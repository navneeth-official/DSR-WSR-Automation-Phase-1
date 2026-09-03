"""Draw reader-friendly annotations on exported slide PNGs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SLIDE_WIDTH_IN = 13.333
DEFAULT_SLIDE_HEIGHT_IN = 7.5


def _in_to_px_x(value_in: float, *, slide_width_in: float, image_width_px: int) -> int:
    return int(round(value_in / slide_width_in * image_width_px))


def _in_to_px_y(value_in: float, *, slide_height_in: float, image_height_px: int) -> int:
    return int(round(value_in / slide_height_in * image_height_px))


def _load_font(size: int = 20) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "Arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _rect_from_position(
    pos: dict[str, Any],
    *,
    slide_width_in: float,
    slide_height_in: float,
    image_width_px: int,
    image_height_px: int,
) -> tuple[int, int, int, int]:
    top = float(pos.get("top") or 0)
    height = float(pos.get("height") or 0)
    width = float(pos.get("width") or slide_width_in * 0.7)
    left = float(pos.get("left") or 0.12)
    x0 = _in_to_px_x(left, slide_width_in=slide_width_in, image_width_px=image_width_px)
    y0 = _in_to_px_y(top, slide_height_in=slide_height_in, image_height_px=image_height_px)
    x1 = _in_to_px_x(left + width, slide_width_in=slide_width_in, image_width_px=image_width_px)
    y1 = _in_to_px_y(top + height, slide_height_in=slide_height_in, image_height_px=image_height_px)
    return x0, y0, x1, y1


def _hl_horizontal_bounds(
    hl_pos: dict[str, Any],
    *,
    slide_width_in: float,
    image_width_px: int,
) -> tuple[int, int]:
    x0 = _in_to_px_x(float(hl_pos.get("left") or 0.12), slide_width_in=slide_width_in, image_width_px=image_width_px)
    x1 = _in_to_px_x(
        float(hl_pos.get("left") or 0.12) + float(hl_pos.get("width") or 8.0),
        slide_width_in=slide_width_in,
        image_width_px=image_width_px,
    )
    return x0, x1


def _ka_horizontal_bounds(
    ka_pos: dict[str, Any],
    *,
    slide_width_in: float,
    image_width_px: int,
) -> tuple[int, int]:
    x0 = _in_to_px_x(float(ka_pos.get("left") or 0.12), slide_width_in=slide_width_in, image_width_px=image_width_px)
    x1 = _in_to_px_x(
        float(ka_pos.get("left") or 0.12) + float(ka_pos.get("width") or 8.0),
        slide_width_in=slide_width_in,
        image_width_px=image_width_px,
    )
    return x0, x1


def _measure_text(font: ImageFont.ImageFont, text: str) -> tuple[int, int]:
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = probe.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _boxes_overlap(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def _draw_callout_label(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    rect: tuple[int, int, int, int],
    label: str,
    color: tuple[int, int, int],
    *,
    canvas_w: int,
    canvas_h: int,
) -> None:
    """Place a readable label beside the highlight — never on top of slide text."""
    if not label.strip():
        return

    x0, y0, x1, y1 = rect
    pad_x, pad_y = 10, 6
    text_w, text_h = _measure_text(font, label)
    box_w = text_w + 2 * pad_x
    box_h = text_h + 2 * pad_y

    candidates = [
        (x1 + 14, y0),
        (x0, y1 + 10),
        (max(8, x0 - box_w - 14), y0),
        (x0, max(8, y0 - box_h - 14)),
    ]

    label_box: tuple[int, int, int, int] | None = None
    for lx, ly in candidates:
        candidate = (lx, ly, lx + box_w, ly + box_h)
        if candidate[0] < 8 or candidate[1] < 8:
            continue
        if candidate[2] > canvas_w - 8 or candidate[3] > canvas_h - 8:
            continue
        if _boxes_overlap(candidate, rect):
            continue
        label_box = candidate
        break

    if label_box is None:
        lx = min(max(x1 + 14, 8), canvas_w - box_w - 8)
        ly = min(max(y0, 8), canvas_h - box_h - 8)
        label_box = (lx, ly, lx + box_w, ly + box_h)

    lx0, ly0, lx1, ly1 = label_box
    draw.rounded_rectangle(
        label_box,
        radius=6,
        fill=(255, 255, 255, 245),
        outline=(*color, 255),
        width=2,
    )
    draw.text((lx0 + pad_x, ly0 + pad_y), label, fill=(*color, 255), font=font)

    anchor_x = lx0 if lx0 >= x1 else lx1
    anchor_y = ly0 + box_h // 2
    target_x = x1 if lx0 >= x1 else x0
    target_y = (y0 + y1) // 2
    draw.line([(anchor_x, anchor_y), (target_x, target_y)], fill=(*color, 180), width=2)


def _draw_highlight_regions(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    regions: list[tuple[tuple[int, int, int, int], str, tuple[int, int, int]]],
    *,
    canvas_w: int,
    canvas_h: int,
) -> None:
    for rect, label, color in regions:
        x0, y0, x1, y1 = rect
        fill = (*color, 40)
        draw.rectangle((x0, y0, x1, y1), outline=(*color, 220), width=4, fill=fill)
        _draw_callout_label(
            draw,
            font,
            rect,
            label,
            color,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
        )


def _rect_from_bounds_in(
    bounds: dict[str, float],
    *,
    slide_width_in: float,
    slide_height_in: float,
    image_width_px: int,
    image_height_px: int,
) -> tuple[int, int, int, int]:
    left = float(bounds.get("left_in") or 0.12)
    top = float(bounds.get("top_in") or 0)
    width = float(bounds.get("width_in") or 8.0)
    height = float(bounds.get("height_in") or 0.2)
    x0 = _in_to_px_x(left, slide_width_in=slide_width_in, image_width_px=image_width_px)
    y0 = _in_to_px_y(top, slide_height_in=slide_height_in, image_height_px=image_height_px)
    x1 = _in_to_px_x(left + width, slide_width_in=slide_width_in, image_width_px=image_width_px)
    y1 = _in_to_px_y(top + height, slide_height_in=slide_height_in, image_height_px=image_height_px)
    return x0, y0, x1, max(y1, y0 + 8)


_ISSUE_LABELS: dict[str, str] = {
    "wrong_font": "Wrong font",
    "wrong_size": "Wrong size",
    "not_bold": "Missing bold",
    "unexpected_bold": "Unexpected bold",
    "wrong_line_spacing": "Wrong line spacing",
    "extra_blanks_after_current_week": "Extra blank line",
    "extra_sprint_gap_blanks": "Extra blank line",
    "sprint_line_spc_bef_high": "Too much space",
}


def _typography_label(detail: dict[str, Any] | None) -> str:
    if not detail:
        return "Typography issue"
    issues = detail.get("issues")
    if isinstance(issues, list) and issues:
        parts = [_ISSUE_LABELS.get(str(issue), str(issue)) for issue in issues]
        seen: set[str] = set()
        unique: list[str] = []
        for part in parts:
            if part not in seen:
                seen.add(part)
                unique.append(part)
        return " · ".join(unique)
    issue = str(detail.get("issue") or "")
    return _ISSUE_LABELS.get(issue, "Typography issue")


def _typography_detail_group_key(detail: dict[str, Any]) -> tuple[Any, ...]:
    paragraph_index = detail.get("paragraph_index")
    role = str(detail.get("role") or "")
    paragraph_text = str(detail.get("paragraph_text") or "")
    run_text = str(detail.get("text") or "").strip()
    if (
        paragraph_text
        and run_text
        and run_text.lower() in paragraph_text.lower()
        and len(run_text) < len(paragraph_text)
    ):
        return ("run", paragraph_index, role, run_text.lower())
    return ("para", paragraph_index, role, paragraph_text[:120])


def _merge_typography_details(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine multiple issue types on the same word/line into one annotation."""
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for detail in details:
        key = _typography_detail_group_key(detail)
        issue = str(detail.get("issue") or "")
        if key not in merged:
            copy = dict(detail)
            copy["issues"] = [issue] if issue else []
            merged[key] = copy
            continue
        bucket = merged[key]
        if issue and issue not in bucket["issues"]:
            bucket["issues"].append(issue)
    return list(merged.values())


def annotate_finding_image(
    source_png: Path,
    output_png: Path,
    finding: dict[str, Any],
    slide_data: dict[str, Any],
    *,
    slide_width_in: float = DEFAULT_SLIDE_WIDTH_IN,
    slide_height_in: float = DEFAULT_SLIDE_HEIGHT_IN,
    footer_limit_in: float = 6.29,
    detail: dict[str, Any] | None = None,
    ppt_path: Path | None = None,
    slide_index: int | None = None,
) -> Path:
    """Draw one annotated PNG for a finding and return the output path."""
    image = Image.open(source_png).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(20)
    w_px, h_px = image.size

    rule_id = finding.get("rule_id", "")
    label = _typography_label(detail) if detail else str(finding.get("annotation_label") or "Check here")
    color = (220, 38, 38)
    regions: list[tuple[tuple[int, int, int, int], str, tuple[int, int, int]]] = []

    hl = slide_data.get("highlights") or {}
    ka = slide_data.get("key_activities")
    hl_pos = hl.get("position_in") or {}
    text_bottom = slide_data.get("rendered_text_bottom_in") or slide_data.get(
        "estimated_text_bottom_in"
    )
    text_top = slide_data.get("hl_text_top_in")
    content_top = slide_data.get("hl_content_top_in") or hl_pos.get("top")

    def _effective_hl_text_top() -> float | None:
        if text_top is not None:
            return float(text_top)
        waste_above = slide_data.get("hl_waste_above_text_in")
        if content_top is not None and waste_above is not None and float(waste_above) > 0:
            return float(content_top) + float(waste_above)
        return None

    def _add_hl_top_region() -> None:
        if not hl_pos or content_top is None:
            return
        effective_text_top = _effective_hl_text_top()
        if effective_text_top is None:
            return
        if float(effective_text_top) - float(content_top) < 0.02:
            return
        x0, x1 = _hl_horizontal_bounds(hl_pos, slide_width_in=slide_width_in, image_width_px=w_px)
        y0 = _in_to_px_y(float(content_top), slide_height_in=slide_height_in, image_height_px=h_px)
        y1 = _in_to_px_y(float(effective_text_top), slide_height_in=slide_height_in, image_height_px=h_px)
        regions.append(((x0, y0, x1, max(y1, y0 + 8)), "Unused top space", (234, 88, 12)))

    def _hl_text_bottom_in() -> float | None:
        if text_bottom is not None:
            return float(text_bottom)
        hl_bottom = hl_pos.get("bottom")
        if hl_bottom is None:
            return None
        waste = slide_data.get("hl_waste_below_text_in")
        if waste is None:
            waste = slide_data.get("hl_box_unused_in")
        if waste is None:
            return None
        return float(hl_bottom) - float(waste)

    def _add_hl_bottom_region() -> None:
        if not hl_pos:
            return
        text_end = _hl_text_bottom_in()
        hl_bottom = hl_pos.get("bottom")
        if text_end is None or hl_bottom is None:
            return
        x0, x1 = _hl_horizontal_bounds(hl_pos, slide_width_in=slide_width_in, image_width_px=w_px)
        y0 = _in_to_px_y(float(text_end), slide_height_in=slide_height_in, image_height_px=h_px)
        y1 = _in_to_px_y(float(hl_bottom), slide_height_in=slide_height_in, image_height_px=h_px)
        if y1 - y0 < 8:
            y1 = y0 + 8
        regions.append(((x0, y0, x1, y1), "Unused bottom space", (234, 88, 12)))

    def _add_ka_top_region() -> None:
        if ka is None:
            return
        ka_pos = ka.get("position_in") or {}
        ka_content_top = slide_data.get("ka_content_top_in") or ka_pos.get("top")
        ka_items = ka.get("item_count") or 0
        if ka_content_top is None or ka_items <= 0:
            return
        ka_top_waste = slide_data.get("ka_waste_above_text_in")
        if ka_top_waste is None or float(ka_top_waste) <= 0:
            return
        text_top_ka = float(ka_content_top) + float(ka_top_waste)
        x0, x1 = _ka_horizontal_bounds(ka_pos, slide_width_in=slide_width_in, image_width_px=w_px)
        y0 = _in_to_px_y(float(ka_content_top), slide_height_in=slide_height_in, image_height_px=h_px)
        y1 = _in_to_px_y(text_top_ka, slide_height_in=slide_height_in, image_height_px=h_px)
        regions.append(((x0, y0, x1, max(y1, y0 + 8)), "Unused top space", (37, 99, 235)))

    def _add_ka_bottom_region() -> None:
        if ka is None:
            return
        ka_pos = ka.get("position_in") or {}
        ka_text_bottom = slide_data.get("ka_rendered_text_bottom_in")
        if ka_text_bottom is None:
            return
        x0, x1 = _ka_horizontal_bounds(ka_pos, slide_width_in=slide_width_in, image_width_px=w_px)
        y0 = _in_to_px_y(float(ka_text_bottom), slide_height_in=slide_height_in, image_height_px=h_px)
        y1 = _in_to_px_y(
            float(ka_pos.get("bottom") or ka_text_bottom),
            slide_height_in=slide_height_in,
            image_height_px=h_px,
        )
        regions.append(((x0, y0, x1, max(y1, y0 + 8)), "Unused bottom space", (37, 99, 235)))

    if rule_id == "HL-TOP-WASTE-01":
        _add_hl_top_region()
    elif rule_id in {"HL-WASTE-01", "CONT-HL-01", "CONT-SPARSE-01", "HL-SIZE-01", "HL-BOTTOM-WASTE-01"}:
        _add_hl_bottom_region()
    elif rule_id == "HL-UTIL-01":
        _add_hl_top_region()
        _add_hl_bottom_region()
    elif rule_id == "KA-TOP-WASTE-01":
        _add_ka_top_region()
    elif rule_id in {"KA-SIZE-01", "KA-BOTTOM-WASTE-01"}:
        _add_ka_bottom_region()
    elif rule_id == "KA-UTIL-01":
        _add_ka_top_region()
        _add_ka_bottom_region()

    rect: tuple[int, int, int, int] | None = None

    if not regions and rule_id in {"HL-BOTTOM-WASTE-01", "HL-UTIL-01"} and hl_pos:
        text_end = _hl_text_bottom_in()
        hl_bottom = hl_pos.get("bottom")
        if text_end is not None and hl_bottom is not None:
            x0, x1 = _hl_horizontal_bounds(hl_pos, slide_width_in=slide_width_in, image_width_px=w_px)
            y0 = _in_to_px_y(float(text_end), slide_height_in=slide_height_in, image_height_px=h_px)
            y1 = _in_to_px_y(float(hl_bottom), slide_height_in=slide_height_in, image_height_px=h_px)
            rect = (x0, y0, x1, max(y1, y0 + 8))
            color = (234, 88, 12)
            label = "Unused bottom space"

    if not regions and rule_id in {"HL-WASTE-01", "CONT-HL-01", "CONT-SPARSE-01", "HL-SIZE-01"} and hl_pos:
        text_end = _hl_text_bottom_in()
        if text_end is not None:
            x0, _, x1, _ = _rect_from_position(
                hl_pos,
                slide_width_in=slide_width_in,
                slide_height_in=slide_height_in,
                image_width_px=w_px,
                image_height_px=h_px,
            )
            y0 = _in_to_px_y(float(text_end), slide_height_in=slide_height_in, image_height_px=h_px)
            y1 = _in_to_px_y(
                float(hl_pos.get("bottom") or text_end),
                slide_height_in=slide_height_in,
                image_height_px=h_px,
            )
            rect = (x0, y0, x1, max(y1, y0 + 8))
            color = (234, 88, 12)
            label = "Empty space here"

    elif rule_id in {"KA-OVERLAP-01", "HL-OVERFLOW-01"} and ka and hl_pos:
        ka_pos = ka.get("position_in") or {}
        overlap_top = float(text_bottom or hl_pos.get("bottom") or ka_pos.get("top") or 0)
        overlap_bottom = float(ka_pos.get("top") or overlap_top + 0.4)
        x0 = _in_to_px_x(float(hl_pos.get("left") or 0.12), slide_width_in=slide_width_in, image_width_px=w_px)
        x1 = _in_to_px_x(
            float(hl_pos.get("left") or 0.12) + float(hl_pos.get("width") or 8.0),
            slide_width_in=slide_width_in,
            image_width_px=w_px,
        )
        y0 = _in_to_px_y(overlap_top, slide_height_in=slide_height_in, image_height_px=h_px)
        y1 = _in_to_px_y(overlap_bottom + 0.25, slide_height_in=slide_height_in, image_height_px=h_px)
        rect = (x0, y0, x1, y1)
        label = "Overlapping"

    elif rule_id == "GEO-02":
        ka_pos = (ka or {}).get("position_in") or hl_pos
        if ka_pos:
            x0 = _in_to_px_x(float(ka_pos.get("left") or 0.12), slide_width_in=slide_width_in, image_width_px=w_px)
            x1 = _in_to_px_x(
                float(ka_pos.get("left") or 0.12) + 4.8,
                slide_width_in=slide_width_in,
                image_width_px=w_px,
            )
            y_footer = _in_to_px_y(footer_limit_in, slide_height_in=slide_height_in, image_height_px=h_px)
            y_ka = _in_to_px_y(
                float(ka_pos.get("bottom") or footer_limit_in),
                slide_height_in=slide_height_in,
                image_height_px=h_px,
            )
            rect = (x0, min(y_ka - 20, y_footer - 30), x1, y_footer)
            label = "Too close to footer"

    elif rule_id == "KA-PLC-02" and hl_pos and ka:
        ka_pos = ka.get("position_in") or {}
        hl_bottom = float(hl_pos.get("bottom") or 0)
        ka_top = float(ka_pos.get("top") or hl_bottom)
        x0 = _in_to_px_x(float(hl_pos.get("left") or 0.12), slide_width_in=slide_width_in, image_width_px=w_px)
        x1 = _in_to_px_x(
            float(hl_pos.get("left") or 0.12) + float(hl_pos.get("width") or 8.0),
            slide_width_in=slide_width_in,
            image_width_px=w_px,
        )
        y0 = _in_to_px_y(hl_bottom, slide_height_in=slide_height_in, image_height_px=h_px)
        y1 = _in_to_px_y(ka_top, slide_height_in=slide_height_in, image_height_px=h_px)
        rect = (x0, y0, x1, max(y1, y0 + 8))
        color = (37, 99, 235)
        label = "HL–KA gap"

    elif rule_id.startswith("CONTENT-KA") and ka:
        ka_pos = ka.get("position_in") or {}
        if ka_pos:
            rect = _rect_from_position(
                ka_pos,
                slide_width_in=slide_width_in,
                slide_height_in=slide_height_in,
                image_width_px=w_px,
                image_height_px=h_px,
            )
            label = "Clear this text"

    elif detail and str(rule_id).startswith(("HL-P", "HL-HDR", "HL-SPC")):
        from app.validation.paragraph_bounds import (
            resolve_hl_paragraph_rect_in,
            resolve_hl_spacing_blank_regions,
        )

        if rule_id == "HL-SPC-03":
            from app.validation.paragraph_bounds import merge_hl_bounds_in

            blank_bounds = resolve_hl_spacing_blank_regions(
                slide_data,
                detail,
                ppt_path=ppt_path,
                slide_index=slide_index,
            )
            merged = merge_hl_bounds_in(blank_bounds)
            if merged:
                rect_px = _rect_from_bounds_in(
                    merged,
                    slide_width_in=slide_width_in,
                    slide_height_in=slide_height_in,
                    image_width_px=w_px,
                    image_height_px=h_px,
                )
                regions.append((rect_px, "Extra blank line", (234, 88, 12)))
            elif not regions:
                bounds = resolve_hl_paragraph_rect_in(
                    slide_data,
                    detail,
                    ppt_path=ppt_path,
                    slide_index=slide_index,
                )
                if bounds:
                    rect = _rect_from_bounds_in(
                        bounds,
                        slide_width_in=slide_width_in,
                        slide_height_in=slide_height_in,
                        image_width_px=w_px,
                        image_height_px=h_px,
                    )
                    label = _typography_label(detail)
                    color = (234, 88, 12)
        else:
            bounds = resolve_hl_paragraph_rect_in(
                slide_data,
                detail,
                ppt_path=ppt_path,
                slide_index=slide_index,
            )
            if bounds:
                rect = _rect_from_bounds_in(
                    bounds,
                    slide_width_in=slide_width_in,
                    slide_height_in=slide_height_in,
                    image_width_px=w_px,
                    image_height_px=h_px,
                )
                label = _typography_label(detail)
                color = (220, 38, 38)

    elif hl_pos and not str(rule_id).startswith(("HL-P", "HL-HDR", "HL-SPC")) and rule_id not in {
        "HL-TOP-WASTE-01",
        "HL-UTIL-01",
        "HL-WASTE-01",
        "HL-BOTTOM-WASTE-01",
        "CONT-HL-01",
        "CONT-SPARSE-01",
        "HL-SIZE-01",
        "HL-SPC-03",
        "KA-TOP-WASTE-01",
        "KA-UTIL-01",
        "KA-BOTTOM-WASTE-01",
        "KA-SIZE-01",
    }:
        rect = _rect_from_position(
            hl_pos,
            slide_width_in=slide_width_in,
            slide_height_in=slide_height_in,
            image_width_px=w_px,
            image_height_px=h_px,
        )
        color = (37, 99, 235)

    if regions:
        _draw_highlight_regions(draw, font, regions, canvas_w=w_px, canvas_h=h_px)
    elif rect:
        x0, y0, x1, y1 = rect
        fill = (*color, 40)
        draw.rectangle((x0, y0, x1, y1), outline=(*color, 220), width=4, fill=fill)
        _draw_callout_label(
            draw,
            font,
            rect,
            label,
            color,
            canvas_w=w_px,
            canvas_h=h_px,
        )

    output_png.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(image, overlay).convert("RGB").save(output_png)
    return output_png


def _typography_details(finding: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = finding.get("metrics") or {}
    paragraphs = metrics.get("paragraphs")
    if isinstance(paragraphs, list) and paragraphs:
        return paragraphs
    details = finding.get("details")
    if isinstance(details, list):
        return details
    return []


def _typography_issue_details(finding: dict[str, Any]) -> list[dict[str, Any]]:
    issues = {
        "wrong_font",
        "wrong_size",
        "not_bold",
        "unexpected_bold",
        "wrong_line_spacing",
    }
    return [detail for detail in _typography_details(finding) if detail.get("issue") in issues]


def _spacing_issue_details(finding: dict[str, Any]) -> list[dict[str, Any]]:
    issues = {
        "extra_blanks_after_current_week",
        "extra_sprint_gap_blanks",
        "sprint_line_spc_bef_high",
    }
    return [detail for detail in _typography_details(finding) if detail.get("issue") in issues]


def annotate_findings(
    ppt_path: Path,
    findings: list[dict[str, Any]],
    slides_by_index: dict[int, dict[str, Any]],
    output_dir: Path,
    *,
    slide_width_in: float = DEFAULT_SLIDE_WIDTH_IN,
    slide_height_in: float = DEFAULT_SLIDE_HEIGHT_IN,
    footer_limit_in: float = 6.29,
) -> dict[tuple[int, str], Path]:
    """Export PNGs and annotate findings."""
    from app.services.ppt_slide_images import export_slides_to_png

    slide_indices = sorted(
        {
            int(f["slide_index"])
            for f in findings
            if f.get("slide_index") is not None
        }
    )
    if not slide_indices:
        return {}

    png_dir = output_dir / "_slides"
    exported = export_slides_to_png(ppt_path, png_dir, slide_indices=slide_indices)
    png_by_index = {int(item["slide_index"]): Path(item["image_path"]) for item in exported}

    annotated: dict[tuple[int, str], Path] = {}
    for finding in findings:
        slide_index = finding.get("slide_index")
        rule_id = finding.get("rule_id")
        if slide_index is None or not rule_id:
            continue
        source = png_by_index.get(int(slide_index))
        if source is None or not source.is_file():
            continue
        slug = str(rule_id).replace("/", "-").lower()
        slide_data = slides_by_index.get(int(slide_index), {})

        typo_details = _merge_typography_details(_typography_issue_details(finding))
        if typo_details:
            finding_images: list[str] = []
            raw_details = _typography_issue_details(finding)
            for issue_num, detail in enumerate(typo_details, start=1):
                out = output_dir / f"slide_{int(slide_index)}_{slug}_issue{issue_num}.png"
                annotate_finding_image(
                    source,
                    out,
                    finding,
                    slide_data,
                    slide_width_in=slide_width_in,
                    slide_height_in=slide_height_in,
                    footer_limit_in=footer_limit_in,
                    detail=detail,
                    ppt_path=ppt_path,
                    slide_index=int(slide_index),
                )
                annotated[(int(slide_index), f"{rule_id}#{issue_num}")] = out
                image_path = str(out)
                finding_images.append(image_path)
                detail["image"] = image_path
                group_key = _typography_detail_group_key(detail)
                for raw in raw_details:
                    if _typography_detail_group_key(raw) == group_key:
                        raw["image"] = image_path
            finding["images"] = finding_images
            finding["image"] = finding_images[0] if finding_images else None
            continue

        spacing_details = _spacing_issue_details(finding)
        if spacing_details:
            finding_images: list[str] = []
            for issue_num, detail in enumerate(spacing_details, start=1):
                out = output_dir / f"slide_{int(slide_index)}_{slug}_issue{issue_num}.png"
                if issue_num == 1 and len(spacing_details) == 1:
                    out = output_dir / f"slide_{int(slide_index)}_{slug}.png"
                annotate_finding_image(
                    source,
                    out,
                    finding,
                    slide_data,
                    slide_width_in=slide_width_in,
                    slide_height_in=slide_height_in,
                    footer_limit_in=footer_limit_in,
                    detail=detail,
                    ppt_path=ppt_path,
                    slide_index=int(slide_index),
                )
                annotated[(int(slide_index), f"{rule_id}#{issue_num}")] = out
                image_path = str(out)
                finding_images.append(image_path)
                detail["image"] = image_path
            finding["images"] = finding_images
            finding["image"] = finding_images[0] if finding_images else None
            continue

        out = output_dir / f"slide_{int(slide_index)}_{slug}.png"
        annotate_finding_image(
            source,
            out,
            finding,
            slide_data,
            slide_width_in=slide_width_in,
            slide_height_in=slide_height_in,
            footer_limit_in=footer_limit_in,
            ppt_path=ppt_path,
            slide_index=int(slide_index),
        )
        annotated[(int(slide_index), str(rule_id))] = out
        finding["image"] = str(out)
    return annotated


def attach_typography_images_to_summaries(
    findings: list[dict[str, Any]],
    slide_summaries: list[dict[str, Any]],
) -> None:
    """Copy annotated PNG paths onto paragraph audit rows in slide summaries."""
    images_by_index: dict[tuple[int, int], str] = {}
    images_by_text: dict[tuple[int, str], str] = {}
    for finding in findings:
        slide_index = finding.get("slide_index")
        if slide_index is None:
            continue
        for detail in _merge_typography_details(_typography_issue_details(finding)):
            image = detail.get("image")
            if not image:
                continue
            para_index = detail.get("paragraph_index")
            if isinstance(para_index, int):
                images_by_index[(int(slide_index), para_index)] = str(image)
            paragraph_text = str(detail.get("paragraph_text") or detail.get("text") or "").strip()
            if paragraph_text:
                images_by_text[(int(slide_index), paragraph_text)] = str(image)

    for summary in slide_summaries:
        slide_index = int(summary.get("slide_index") or 0)
        typography = (summary.get("checks") or {}).get("typography") or {}
        for row in typography.get("paragraphs_audited") or []:
            if row.get("status") != "fix":
                continue
            para_index = row.get("paragraph_index")
            if isinstance(para_index, int):
                image = images_by_index.get((slide_index, para_index))
                if image:
                    row["image"] = image
                    continue
            preview = str(row.get("text_preview") or "").replace("…", "").strip()
            image = images_by_text.get((slide_index, preview))
            if not image:
                for (idx, text), path in images_by_text.items():
                    if idx != slide_index:
                        continue
                    if text and (preview.startswith(text[:24]) or text.startswith(preview[:24])):
                        image = path
                        break
            if image:
                row["image"] = image
