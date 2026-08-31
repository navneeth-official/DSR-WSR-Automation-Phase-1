"""Tests for title format and contd marker detection."""

from __future__ import annotations

from app.wsr_engine.models import SlideDescriptor
from app.wsr_engine.project_detector import detect_contd_marker, detect_title_format


def test_detect_contd_marker_two_dots():
    assert detect_contd_marker("Delivery Status - Cost (Contd..)") == "(Contd..)"


def test_detect_contd_marker_ellipsis():
    assert detect_contd_marker("Delivery status – Supplier (Contd…)").lower().startswith("(contd")


def test_detect_title_format_hyphen():
    slides = [
        SlideDescriptor(0, "Delivery Status - Cost Core Service", "PROJECT_MAIN", "Cost Core Service"),
    ]
    fmt = detect_title_format(slides)
    assert fmt.separator == " - "
    assert "Status" in fmt.prefix or "status" in fmt.prefix
