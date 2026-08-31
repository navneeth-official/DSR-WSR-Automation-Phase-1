"""Deterministic PowerPoint layout correction."""

from app.layout.config import LayoutCorrectorConfig
from app.layout.corrector import LayoutCorrector
from app.layout.exceptions import LayoutCorrectionError, LayoutFailureError
from app.layout.measurement_mapper import VisionFieldMapping, VISION_FIELD_MAPPINGS, VisionMeasurementMapper
from app.layout.shape_ops import (
    PixelScale,
    expand_table_height,
    maintain_alignment,
    maintain_gap,
    move_shape,
    read_png_dimensions,
    resize_shape,
    resize_table_shape,
    restore_template_position,
    shrink_table_height,
)
from app.layout.template_geometry import TemplateGeometry, TemplateGeometryProvider
from app.layout.types import (
    CorrectionAction,
    CorrectionActionType,
    LayoutCorrectionResult,
    SlideCorrectionInput,
    SlideCorrectionResult,
)

__all__ = [
    "CorrectionAction",
    "CorrectionActionType",
    "LayoutCorrectionError",
    "LayoutCorrectionResult",
    "LayoutCorrector",
    "LayoutCorrectorConfig",
    "LayoutFailureError",
    "PixelScale",
    "SlideCorrectionInput",
    "SlideCorrectionResult",
    "TemplateGeometry",
    "TemplateGeometryProvider",
    "VISION_FIELD_MAPPINGS",
    "VisionFieldMapping",
    "VisionMeasurementMapper",
    "expand_table_height",
    "maintain_alignment",
    "maintain_gap",
    "move_shape",
    "read_png_dimensions",
    "resize_shape",
    "resize_table_shape",
    "restore_template_position",
    "shrink_table_height",
]
