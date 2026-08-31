"""Filesystem helpers that tolerate Windows / OneDrive file locks."""

from __future__ import annotations

import os
import shutil
import stat
import time
from pathlib import Path


def _clear_readonly(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass


def _on_rm_error(func, path, _exc_info) -> None:
    _clear_readonly(Path(path))
    func(path)


def unlink_file(path: Path) -> None:
    """Delete a single file, clearing read-only when needed."""
    if not path.is_file():
        return
    _clear_readonly(path)
    path.unlink(missing_ok=True)


def clear_preview_pngs(preview_dir: Path) -> None:
    """Delete slide_*.png files without removing the preview directory itself."""
    if not preview_dir.is_dir():
        return
    for png in preview_dir.glob("slide_*.png"):
        unlink_file(png)


def prepare_preview_directory(preview_dir: Path) -> None:
    """
    Ensure a preview directory exists and stale PNGs are removed.

    Reuses the existing folder instead of rmtree to avoid WinError 5 when
    OneDrive or the browser still holds handles on prior preview images.
    """
    preview_dir.mkdir(parents=True, exist_ok=True)
    clear_preview_pngs(preview_dir)


def remove_directory(path: Path, *, retries: int = 3) -> None:
    """Best-effort directory removal with Windows/OneDrive retry handling."""
    if not path.exists():
        return

    delay_s = 0.25
    last_error: OSError | None = None
    for attempt in range(retries):
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            return
        except OSError as exc:
            last_error = exc
            clear_preview_pngs(path) if path.is_dir() else None
            if attempt + 1 < retries:
                time.sleep(delay_s)
                delay_s *= 2

    if path.is_dir():
        clear_preview_pngs(path)
        try:
            remaining = list(path.iterdir())
        except OSError:
            remaining = ["<unreadable>"]
        if not remaining:
            try:
                path.rmdir()
                return
            except OSError as exc:
                last_error = exc

    if last_error is not None:
        raise last_error
