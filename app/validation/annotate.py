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


def annotate_finding_image(
    source_png: Path,
    output_png: Path,
    finding: dict[str, Any],
    slide_data: dict[str, Any],
    *,
    slide_width_in: float = DEFAULT_SLIDE_WIDTH_IN,
    slide_height_in: float = DEFAULT_SLIDE_HEIGHT_IN,
    footer_limit_in: float = 6.29,
) -> Path:
    """Draw one annotated PNG for a finding and return the output path."""
    image = Image.open(source_png).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(20)
    w_px, h_px = image.size

    rule_id = finding.get("rule_id", "")
    label = str(finding.get("annotation_label") or "Check here")
    color = (220, 38, 38)

    hl = slide_data.get("highlights") or {}
    ka = slide_data.get("key_activities")
    hl_pos = hl.get("position_in") or {}
    text_bottom = slide_data.get("rendered_text_bottom_in") or slide_data.get(
        "estimated_text_bottom_in"
    )

    rect: tuple[int, int, int, int] | None = None

    if rule_id in {"HL-WASTE-01", "CONT-HL-01", "CONT-SPARSE-01", "HL-SIZE-01"} and hl_pos:
        if text_bottom is not None:
            x0, _, x1, _ = _rect_from_position(
                hl_pos,
                slide_width_in=slide_width_in,
                slide_height_in=slide_height_in,
                image_width_px=w_px,
                image_height_px=h_px,
            )
            y0 = _in_to_px_y(float(text_bottom), slide_height_in=slide_height_in, image_height_px=h_px)
            y1 = _in_to_px_y(
                float(hl_pos.get("bottom") or text_bottom),
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

    elif hl_pos:
        rect = _rect_from_position(
            hl_pos,
            slide_width_in=slide_width_in,
            slide_height_in=slide_height_in,
            image_width_px=w_px,
            image_height_px=h_px,
        )
        color = (37, 99, 235)

    if rect:
        x0, y0, x1, y1 = rect
        fill = (*color, 40)
        draw.rectangle((x0, y0, x1, y1), outline=(*color, 220), width=4, fill=fill)
        draw.text((x0 + 8, max(8, y0 - 28)), label, fill=(*color, 255), font=font)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(image, overlay).convert("RGB").save(output_png)
    return output_png


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
        out = output_dir / f"slide_{int(slide_index)}_{slug}.png"
        annotate_finding_image(
            source,
            out,
            finding,
            slides_by_index.get(int(slide_index), {}),
            slide_width_in=slide_width_in,
            slide_height_in=slide_height_in,
            footer_limit_in=footer_limit_in,
        )
        annotated[(int(slide_index), str(rule_id))] = out
        finding["image"] = str(out)
    return annotated
