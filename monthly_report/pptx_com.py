"""PowerPoint COM helpers (Windows) — reliable save and slide duplicate."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def com_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    return True


def _dispatch_powerpoint():
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")
    ppt.Visible = 1
    ppt.DisplayAlerts = 0
    return ppt


def _open_presentation(ppt, path: Path, *, repair: bool = False):
    resolved = str(path.resolve())
    if repair:
        # msoTrue = -1 for OpenAndRepair (PowerPoint 2007+)
        return ppt.Presentations.Open(
            resolved,
            ReadOnly=False,
            Untitled=False,
            WithWindow=True,
            OpenAndRepair=-1,
        )
    return ppt.Presentations.Open(
        resolved,
        ReadOnly=False,
        Untitled=False,
        WithWindow=True,
    )


def _save_as_via_powerpoint(source_path: Path, dest_path: Path) -> None:
    """Open ``source_path`` in PowerPoint and SaveAs ``dest_path`` (repairs OPC issues)."""
    ppt = _dispatch_powerpoint()
    presentation = None
    try:
        try:
            presentation = _open_presentation(ppt, source_path)
        except Exception:
            presentation = _open_presentation(ppt, source_path, repair=True)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        presentation.SaveAs(str(dest_path.resolve()))
    finally:
        if presentation is not None:
            presentation.Close()
        ppt.Quit()


def resave_via_powerpoint(ppt_path: Path) -> None:
    """
    Open a deck in PowerPoint and save it again.

    Fixes OPC/package issues from python-pptx (duplicate slide parts, repair prompts).
    """
    path = Path(ppt_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    ppt = _dispatch_powerpoint()
    presentation = _open_presentation(ppt, path)
    try:
        presentation.Save()
    finally:
        presentation.Close()
        ppt.Quit()


def _goto_slide(presentation, slide_index_1based: int) -> None:
    if presentation.Windows.Count < 1:
        presentation.NewWindow()
    window = presentation.Windows(1)
    window.Activate()
    window.View.GotoSlide(slide_index_1based)


def _duplicate_slide_before(
    presentation,
    source_slide_1based: int,
    insert_before_1based: int,
) -> None:
    """
    Insert a copy of ``source_slide_1based`` immediately before ``insert_before_1based``.

    Prefer Copy/Paste in the active PowerPoint session (clipboard is not reliable across
    separate Application instances). Fall back to Duplicate + MoveTo when Paste fails.
    """
    slides = presentation.Slides
    count = int(slides.Count)
    if source_slide_1based < 1 or source_slide_1based > count:
        raise ValueError(f"Source slide {source_slide_1based} out of range (1..{count})")
    if insert_before_1based < 1 or insert_before_1based > count + 1:
        raise ValueError(
            f"Insert index {insert_before_1based} out of range (1..{count + 1})"
        )

    _goto_slide(presentation, source_slide_1based)
    try:
        slides(source_slide_1based).Copy()
        time.sleep(0.05)
        slides.Paste(Index=insert_before_1based)
        return
    except Exception:
        pass

    dup_range = slides(source_slide_1based).Duplicate()
    new_index = int(dup_range.SlideIndex)
    if new_index != insert_before_1based:
        slides(new_index).MoveTo(insert_before_1based)


def duplicate_slide_before_index_com(
    ppt_path: Path,
    source_slide_1based: int,
    insert_before_1based: int,
) -> None:
    """Duplicate one slide in its own short-lived PowerPoint session (prefer batch API)."""
    path = Path(ppt_path).resolve()
    ppt = _dispatch_powerpoint()
    presentation = _open_presentation(ppt, path)
    try:
        _duplicate_slide_before(presentation, source_slide_1based, insert_before_1based)
        presentation.Save()
    finally:
        presentation.Close()
        ppt.Quit()


def materialize_delivery_slides_via_com(
    ppt_path: Path,
    prototype_index_0based: int,
    insert_before_index_0based: int,
    count: int,
) -> None:
    """Create ``count`` delivery slides (unfilled copies of the prototype) using PowerPoint."""
    if count < 1:
        return
    materialize_slides_via_com(
        ppt_path,
        insert_before_index_0based,
        [prototype_index_0based] * count,
    )


def materialize_slides_via_com(
    ppt_path: Path,
    insert_before_index_0based: int,
    source_indices_0based: list[int],
) -> None:
    """
    Ensure the deck contains one slide per entry in ``source_indices_0based``.

    The first occurrence of each prototype index is assumed to already exist in the
    template; further copies are duplicated via PowerPoint and inserted before
    ``insert_before_index_0based`` (which shifts right after each insert).
    """
    if not source_indices_0based:
        return
    path = Path(ppt_path).resolve()
    ppt = _dispatch_powerpoint()
    presentation = _open_presentation(ppt, path)
    try:
        insert_before = insert_before_index_0based + 1
        seen: dict[int, int] = {}
        for source_index in source_indices_0based:
            seen[source_index] = seen.get(source_index, 0) + 1
            if seen[source_index] == 1:
                continue
            _duplicate_slide_before(presentation, source_index + 1, insert_before)
            insert_before += 1
        presentation.Save()
    finally:
        presentation.Close()
        ppt.Quit()


def save_presentation(path: Path, prs) -> str | None:
    """Save with python-pptx, validate, then re-save via COM on Windows when available."""
    from pptx import Presentation

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.pptx")
    prs.save(str(tmp))
    try:
        Presentation(str(tmp))
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"python-pptx produced an invalid PowerPoint file ({exc}). "
            "This usually means a duplicated delivery/chart slide corrupted the package."
        ) from exc
    if os.environ.get("MSR_SKIP_COM_RESAVE", "").lower() in ("1", "true", "yes"):
        tmp.replace(path)
        return None
    if not com_available():
        tmp.replace(path)
        return None
    try:
        _save_as_via_powerpoint(tmp, path)
        tmp.unlink(missing_ok=True)
        return None
    except Exception as exc:
        # Keep python-pptx output if PowerPoint cannot open/re-save (better than no file).
        tmp.replace(path)
        return (
            f"Deck saved to {path} but PowerPoint could not re-save ({exc}). "
            "If PowerPoint prompts to Repair when opening, accept Repair and save again."
        )
