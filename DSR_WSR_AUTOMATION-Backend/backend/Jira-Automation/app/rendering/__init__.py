"""PowerPoint slide rendering (PPTX → PNG)."""

from app.rendering.com_backend import ComSlideRendererBackend
from app.rendering.factory import get_slide_renderer_backend
from app.rendering.libreoffice_backend import LibreOfficeSlideRendererBackend
from app.rendering.powerpoint_renderer import PowerPointRenderer
from app.rendering.protocol import SlideRendererBackend
from app.rendering.remote_backend import RemoteSlideRendererBackend

__all__ = [
    "ComSlideRendererBackend",
    "LibreOfficeSlideRendererBackend",
    "RemoteSlideRendererBackend",
    "PowerPointRenderer",
    "SlideRendererBackend",
    "get_slide_renderer_backend",
]
