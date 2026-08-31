"""PowerPoint slide rendering (PPTX → PNG)."""

from app.rendering.com_backend import ComSlideRendererBackend
from app.rendering.factory import get_slide_renderer_backend
from app.rendering.libreoffice_backend import LibreOfficeSlideRendererBackend
from app.rendering.powerpoint_renderer import PowerPointRenderer
from app.rendering.protocol import SlideRendererBackend

__all__ = [
    "ComSlideRendererBackend",
    "LibreOfficeSlideRendererBackend",
    "PowerPointRenderer",
    "SlideRendererBackend",
    "get_slide_renderer_backend",
]
