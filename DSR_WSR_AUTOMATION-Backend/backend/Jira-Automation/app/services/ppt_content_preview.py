"""Human-readable preview of PPT slide content (mirrors deck Highlights layout)."""

from __future__ import annotations

from typing import Any

from app.constants.ppt_bullets import CATEGORY_HEADER_PREVIEW_SYMBOL
from app.services.sprint_display import sprint_dates_from_section


def _sprint_line(section: dict[str, Any]) -> str:
    total = (
        len(section["released"])
        + len(section["inprogress"])
        + len(section["completed"])
    )
    status = section.get("sprint_status", "In-progress")
    sprint_dates = sprint_dates_from_section(section)
    return (
        f"Sprint – {section['sprint_name']}, {status} "
        f"({sprint_dates}) Stories "
        f"(Total – {total}, Done – {len(section['completed'])}, "
        f"In-review – {len(section['released'])}, "
        f"In-progress – {len(section['inprogress'])})"
    )


def _bullet_section(label: str, items: list[str]) -> list[str]:
    # Preview symbol ► = G10X Wingdings Ø arrowhead on the real slide
    lines = [f"  {CATEGORY_HEADER_PREVIEW_SYMBOL} {label} – {len(items)} stories"]
    for item in items:
        lines.append(f"    - {item}")
    return lines


def _slide_sections(slide: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize slide to a list of sprint sections."""
    if slide.get("sections"):
        return slide["sections"]
    return [
        {
            "sprint_name": slide["sprint_name"],
            "sprint_dates": slide["sprint_dates"],
            "sprint_status": slide.get("sprint_status", "In-progress"),
            "released": slide.get("released", []),
            "inprogress": slide.get("inprogress", []),
            "completed": slide.get("completed", []),
        }
    ]


def format_slide_preview(slide: dict[str, Any]) -> str:
    """Format one delivery-status slide as plain text."""
    lines = [
        "=" * 72,
        f"Delivery status – {slide['title']}",
        f"Project: {slide.get('project_name', '')} ({slide.get('project_key', '')})",
        "=" * 72,
        "",
        "HIGHLIGHTS",
        "-" * 40,
    ]

    for section in _slide_sections(slide):
        lines.append(_sprint_line(section))
        lines.append("")
        lines.append("  Current week sprint status")
        lines.append("")
        if section["released"]:
            lines.extend(_bullet_section("Stories released for partner review", section["released"]))
            lines.append("")
        if section["inprogress"]:
            lines.extend(_bullet_section("Stories in-progress this week", section["inprogress"]))
            lines.append("")
        if section["completed"]:
            lines.extend(_bullet_section("Stories completed this week", section["completed"]))
            lines.append("")

    ka = slide.get("key_activities") or []
    lines.append("KEY ACTIVITIES FOR NEXT WEEK")
    lines.append("-" * 40)
    if ka:
        for item in ka:
            lines.append(f"  - {item}")
    else:
        lines.append("  (empty — reserved for manual BSA entry)")
    lines.append("")
    return "\n".join(lines)


def format_content_preview(content: dict[str, Any]) -> str:
    """Format full ppt_content payload for review before deck build."""
    header = [
        "WSR PPT CONTENT PREVIEW",
        f"Report period: {content.get('report_start_date', '')} – {content.get('report_end_date', '')}",
        f"Stories: {content.get('meta', {}).get('story_count', '?')}",
        f"Slides:  {content.get('meta', {}).get('slide_count', '?')}",
        "",
    ]
    body = [format_slide_preview(s) for s in content.get("slides", [])]
    return "\n".join(header + body)
