"""Layout correction exceptions."""

from __future__ import annotations


class LayoutCorrectionError(Exception):
    """Base error for layout correction failures."""


class LayoutFailureError(LayoutCorrectionError):
    """Raised when a correction cannot be applied within template constraints."""

    def __init__(self, message: str, *, slide_number: int | None = None) -> None:
        super().__init__(message)
        self.slide_number = slide_number
