"""PowerPoint COM APIs for rendered text bounding boxes (Windows)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

POINTS_PER_INCH = 72.0
EMU_PER_POINT = 12700  # 914400 / 72


@dataclass(frozen=True)
class ComHlTextBounds:
    """Rendered Highlights content-cell text bounds from PowerPoint COM."""

    text_bottom_in: float
    hl_bottom_in: float
    hl_top_in: float
    waste_in: float
    content_top_in: float
    content_bottom_in: float
    content_left_in: float
    content_right_in: float
    method: str = "com"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_bottom_in": self.text_bottom_in,
            "hl_bottom_in": self.hl_bottom_in,
            "hl_top_in": self.hl_top_in,
            "waste_in": self.waste_in,
            "content_top_in": self.content_top_in,
            "content_bottom_in": self.content_bottom_in,
            "content_left_in": self.content_left_in,
            "content_right_in": self.content_right_in,
            "method": self.method,
        }


def _set_powerpoint_visible(app, *, visible: bool) -> None:
    try:
        app.Visible = -1 if visible else 0
    except Exception:
        try:
            app.Visible = 1 if visible else 0
        except Exception:
            app.Visible = 1


def _iter_hl_shapes(slide: Any) -> Iterator[Any]:
    for shape_id in (9, 7):
        for idx in range(1, int(slide.Shapes.Count) + 1):
            shape = slide.Shapes(idx)
            if int(shape.Id) != shape_id or not shape.HasTable:
                continue
            if int(shape.Table.Rows.Count) == 3:
                yield shape


def _absolute_text_bottom_pt(cell_shape: Any, text_range: Any) -> float | None:
    """
    Slide-absolute text bottom in points.

    Table-cell TextRange BoundTop/BoundHeight are relative to the cell shape;
    add cell_shape.Top for slide coordinates.
    """
    text = str(text_range.Text or "").strip()
    if not text:
        return None
    try:
        rel_bottom = float(text_range.BoundTop) + float(text_range.BoundHeight)
    except Exception:
        return None
    if rel_bottom <= 0:
        return None
    return float(cell_shape.Top) + rel_bottom


def _paragraph_max_bottom_pt(cell_shape: Any, text_range: Any) -> float | None:
    """Max slide-absolute bottom across non-empty paragraphs."""
    best: float | None = None
    try:
        paras = text_range.Paragraphs
        count = int(paras.Count)
    except Exception:
        return _absolute_text_bottom_pt(cell_shape, text_range)

    for i in range(1, count + 1):
        try:
            para = paras.Item(i)
        except Exception:
            continue
        if not str(para.Text or "").strip():
            continue
        try:
            rel_bottom = float(para.BoundTop) + float(para.BoundHeight)
        except Exception:
            continue
        abs_bottom = float(cell_shape.Top) + rel_bottom
        best = abs_bottom if best is None else max(best, abs_bottom)

    if best is not None:
        return best
    return _absolute_text_bottom_pt(cell_shape, text_range)


def _hl_content_text_bottom_pt(hl_shape: Any) -> float | None:
    """Bottom of visible text in HL content cell (row 3, col 1 — COM 1-based)."""
    cell_shape = hl_shape.Table.Cell(3, 1).Shape
    text_range = None
    for accessor in ("TextFrame2", "TextFrame"):
        try:
            text_range = getattr(cell_shape, accessor).TextRange
            break
        except Exception:
            continue
    if text_range is None:
        return None
    return _paragraph_max_bottom_pt(cell_shape, text_range)


def _hl_content_row_bounds_pt(hl_shape: Any) -> tuple[float, float, float, float]:
    """Content row (COM row 3) bounds in slide points: left, top, right, bottom."""
    tops: list[float] = []
    bottoms: list[float] = []
    for col in range(1, int(hl_shape.Table.Columns.Count) + 1):
        cell_shape = hl_shape.Table.Cell(3, col).Shape
        tops.append(float(cell_shape.Top))
        bottoms.append(float(cell_shape.Top) + float(cell_shape.Height))
    return (
        float(hl_shape.Left),
        min(tops),
        float(hl_shape.Left) + float(hl_shape.Width),
        max(bottoms),
    )


def measure_hl_text_bounds_com(slide: Any) -> ComHlTextBounds | None:
    """Measure HL internal slack using PowerPoint COM BoundTop/BoundHeight."""
    hl_shape = next(_iter_hl_shapes(slide), None)
    if hl_shape is None:
        return None

    text_bottom_pt = _hl_content_text_bottom_pt(hl_shape)
    if text_bottom_pt is None:
        return None

    hl_top_pt = float(hl_shape.Top)
    # Complete Highlights table shape — not content cell (they share the same bottom
    # on a 3-row HL table because row 3 spans the content area to the table edge).
    hl_bottom_pt = hl_top_pt + float(hl_shape.Height)
    content_left_pt, content_top_pt, content_right_pt, content_bottom_pt = (
        _hl_content_row_bounds_pt(hl_shape)
    )
    text_bottom_in = round(text_bottom_pt / POINTS_PER_INCH, 4)
    hl_top_in = round(hl_top_pt / POINTS_PER_INCH, 4)
    hl_bottom_in = round(hl_bottom_pt / POINTS_PER_INCH, 4)
    waste_in = round(max(hl_bottom_in - text_bottom_in, 0.0), 4)

    return ComHlTextBounds(
        text_bottom_in=text_bottom_in,
        hl_bottom_in=hl_bottom_in,
        hl_top_in=hl_top_in,
        waste_in=waste_in,
        content_top_in=round(content_top_pt / POINTS_PER_INCH, 4),
        content_bottom_in=round(content_bottom_pt / POINTS_PER_INCH, 4),
        content_left_in=round(content_left_pt / POINTS_PER_INCH, 4),
        content_right_in=round(content_right_pt / POINTS_PER_INCH, 4),
        method="com",
    )


class ComTextBoundsMeasurer:
    """Batch COM measurement for an open presentation."""

    def __init__(self, ppt_path: str | Path) -> None:
        try:
            import win32com.client  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "win32com is required for COM text bounds. Install pywin32."
            ) from exc

        self._ppt_path = Path(ppt_path).resolve()
        self._win32com = win32com
        self._app = win32com.client.Dispatch("PowerPoint.Application")
        _set_powerpoint_visible(self._app, visible=True)
        self._presentation = self._app.Presentations.Open(
            str(self._ppt_path), WithWindow=False
        )
        self._slide_height_pt = float(self._presentation.PageSetup.SlideHeight)
        self._slide_width_pt = float(self._presentation.PageSetup.SlideWidth)

    @property
    def slide_height_in(self) -> float:
        return round(self._slide_height_pt / POINTS_PER_INCH, 4)

    @property
    def slide_width_in(self) -> float:
        return round(self._slide_width_pt / POINTS_PER_INCH, 4)

    def measure_slide(self, slide_index: int) -> ComHlTextBounds | None:
        if slide_index < 1 or slide_index > int(self._presentation.Slides.Count):
            return None
        return measure_hl_text_bounds_com(self._presentation.Slides(slide_index))

    def close(self) -> None:
        try:
            self._presentation.Close()
        finally:
            self._app.Quit()

    def __enter__(self) -> ComTextBoundsMeasurer:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
