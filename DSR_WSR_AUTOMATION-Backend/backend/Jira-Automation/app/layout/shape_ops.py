"""Low-level deterministic shape operations for layout correction."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pptx.util import Emu

from app.layout.exceptions import LayoutFailureError
from app.services.ppt_layout_metrics import EMU_PER_INCH


@dataclass(frozen=True)
class PixelScale:
    """Map rendered-image pixels to slide EMU coordinates."""

    slide_width_emu: int
    slide_height_emu: int
    image_width_px: int
    image_height_px: int

    @classmethod
    def from_paths(
        cls,
        *,
        slide_width_emu: int,
        slide_height_emu: int,
        image_path: Path | None,
        default_width_px: int = 1920,
        default_height_px: int = 1080,
    ) -> PixelScale:
        width_px, height_px = default_width_px, default_height_px
        if image_path and image_path.is_file():
            width_px, height_px = read_png_dimensions(image_path)
        return cls(
            slide_width_emu=slide_width_emu,
            slide_height_emu=slide_height_emu,
            image_width_px=width_px,
            image_height_px=height_px,
        )

    def px_y_to_emu(self, px: float) -> int:
        if self.image_height_px <= 0:
            return 0
        return int(px * self.slide_height_emu / self.image_height_px)

    def emu_y_to_px(self, emu: int) -> float:
        if self.slide_height_emu <= 0:
            return 0.0
        return emu * self.image_height_px / self.slide_height_emu

    def in_to_emu(self, inches: float) -> int:
        return int(inches * EMU_PER_INCH)


def read_png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG file: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def move_shape(shape, *, top: int | None = None, left: int | None = None) -> None:
    """Move a shape by setting absolute EMU top/left."""
    if top is not None:
        shape.top = int(top)
    if left is not None:
        shape.left = int(left)


def resize_shape(
    shape,
    *,
    height: int | None = None,
    width: int | None = None,
) -> None:
    """Resize a shape's outer bounding box in EMU."""
    if height is not None:
        shape.height = max(int(height), 1)
    if width is not None:
        shape.width = max(int(width), 1)


def resize_table_shape(
    table_shape,
    *,
    row_heights: list[int],
    target_height: int,
    uds_module: Any,
) -> None:
    """Resize a table shape by assigning row heights (pptx resets height on row change)."""
    uds_module._set_table_shape_height(table_shape, row_heights, target_height)


def restore_template_position(
    shape,
    ref_shape,
    *,
    restore_size: bool = True,
) -> None:
    """Restore a shape to its template reference position (and optionally size)."""
    shape.left = ref_shape.left
    shape.top = ref_shape.top
    if restore_size:
        shape.width = ref_shape.width
        shape.height = ref_shape.height


def maintain_alignment(shape, ref_shape) -> None:
    """Align horizontal placement and width to the template reference."""
    shape.left = ref_shape.left
    shape.width = ref_shape.width


def maintain_gap(
    upper_bottom_emu: int,
    lower_shape,
    *,
    min_gap_emu: int,
) -> int:
    """
    Ensure at least ``min_gap_emu`` between an upper section bottom and a lower shape.

    Returns the applied lower-shape top (EMU).
    """
    target_top = upper_bottom_emu + min_gap_emu
    if lower_shape.top < target_top:
        move_shape(lower_shape, top=target_top)
    return lower_shape.top


def shrink_table_height(
    table_shape,
    *,
    delta_emu: int,
    profile: dict[str, Any],
    uds_module: Any,
    min_height: int | None = None,
) -> int:
    """Reduce a 3-row Highlights table height by ``delta_emu`` without going below ``min_height``."""
    r0 = profile["r0"]
    r1 = profile["r1"]
    ref_pad = profile["ref_pad"]
    min_pad = max(int(ref_pad * 0.3), 91440)
    current_h = table_shape.height
    floor = min_height or (r0 + r1 + min_pad + profile.get("ref_r2", 91440) // 4)
    new_h = max(current_h - delta_emu, floor)
    content_h = max(new_h - r0 - r1 - min_pad, profile.get("ref_r2", 91440) // 10)
    resize_table_shape(
        table_shape,
        row_heights=[r0, r1, content_h],
        target_height=new_h,
        uds_module=uds_module,
    )
    return new_h


def expand_table_height(
    table_shape,
    *,
    delta_emu: int,
    profile: dict[str, Any],
    uds_module: Any,
    max_bottom_emu: int,
) -> int:
    """Expand a 3-row Highlights table height by ``delta_emu`` within footer limits."""
    r0 = profile["r0"]
    r1 = profile["r1"]
    ref_pad = profile["ref_pad"]
    current_h = table_shape.height
    new_h = current_h + delta_emu
    if table_shape.top + new_h > max_bottom_emu:
        raise LayoutFailureError(
            f"Cannot expand Highlights to {Emu(new_h).inches:.2f} in "
            f"(footer limit {Emu(max_bottom_emu).inches:.2f} in)"
        )
    content_h = max(new_h - r0 - r1 - ref_pad, table_shape.table.rows[2].height)
    resize_table_shape(
        table_shape,
        row_heights=[r0, r1, content_h],
        target_height=new_h,
        uds_module=uds_module,
    )
    return new_h
