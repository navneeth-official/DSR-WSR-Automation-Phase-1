"""PowerPoint slide rendering (PPTX → PNG)."""

from app.rendering.com_backend import ComSlideRendererBackend
from app.rendering.powerpoint_renderer import PowerPointRenderer
from app.rendering.protocol import SlideRendererBackend

__all__ = [
    "ComSlideRendererBackend",
    "PowerPointRenderer",
    "SlideRendererBackend",
]
