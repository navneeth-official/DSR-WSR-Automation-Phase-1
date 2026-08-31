"""Debug logging for template geometry / ref_ka resolution."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_LOGGER_NAME = "app.layout.geometry"
_configured = False


def get_geometry_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def configure_geometry_logging(*, log_path: Path | None = None) -> logging.Logger:
    global _configured
    logger = get_geometry_logger()
    logger.setLevel(logging.DEBUG)

    if _configured:
        return logger

    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _configured = True
    return logger


def _shape_summary(shape) -> dict[str, Any]:
    info: dict[str, Any] = {
        "shape_id": getattr(shape, "shape_id", None),
        "name": getattr(shape, "name", ""),
        "left": getattr(shape, "left", None),
        "top": getattr(shape, "top", None),
        "width": getattr(shape, "width", None),
        "height": getattr(shape, "height", None),
    }
    if shape.has_table:
        try:
            rows = len(shape.table.rows)
            cols = len(shape.table.columns)
            header = shape.table.cell(0, 0).text.strip()
            info.update(
                {
                    "kind": "table",
                    "rows": rows,
                    "cols": cols,
                    "header_cell": header,
                }
            )
        except (IndexError, AttributeError):
            info["kind"] = "table_unreadable"
    elif shape.has_text_frame:
        info["kind"] = "text"
        info["text_preview"] = shape.text_frame.text.strip()[:80]
    else:
        info["kind"] = "other"
    return info


def log_g10x_shape_inventory(
    *,
    slide_number: int | None,
    slide_title: str,
    service_title: str,
    g10x_slide_index: int,
    g10x_slide_title: str,
    shapes: list,
) -> None:
    logger = get_geometry_logger()
    logger.debug(
        "GEOMETRY slide=%s title=%r service=%r g10x_index=%s g10x_title=%r",
        slide_number,
        slide_title,
        service_title,
        g10x_slide_index,
        g10x_slide_title,
    )
    for shape in shapes:
        logger.debug("  G10X shape: %s", _shape_summary(shape))


def log_ref_ka_resolution(
    *,
    slide_number: int | None,
    slide_title: str,
    service_title: str,
    is_contd: bool,
    g10x_slide_index: int,
    on_slide_ka_in_g10x: bool,
    ref_ka_from_build_profile: bool,
    ref_ka_after_ka_profile: bool,
    ref_ka_source: str,
    reason: str,
    ref_ka_summary: dict[str, Any] | None,
) -> None:
    logger = get_geometry_logger()
    logger.info(
        "REF_KA slide=%s title=%r service=%r contd=%s g10x_index=%s "
        "g10x_on_slide_ka=%s build_profile_has_ka=%s ka_profile_has_ka=%s "
        "source=%s reason=%s ref=%s",
        slide_number,
        slide_title,
        service_title,
        is_contd,
        g10x_slide_index,
        on_slide_ka_in_g10x,
        ref_ka_from_build_profile,
        ref_ka_after_ka_profile,
        ref_ka_source,
        reason,
        ref_ka_summary,
    )


def summarize_ref_shape(shape) -> dict[str, Any] | None:
    if shape is None:
        return None
    summary = _shape_summary(shape)
    if shape.has_table:
        try:
            summary["ka_header"] = shape.table.cell(0, 0).text.strip()
        except (IndexError, AttributeError):
            pass
    return summary
