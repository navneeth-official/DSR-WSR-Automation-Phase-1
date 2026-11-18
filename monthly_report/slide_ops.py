"""Slide-level operations python-pptx does not provide (duplicate, move, remove)."""

from __future__ import annotations

from copy import deepcopy

from lxml import etree
from pptx.oxml.ns import qn

_RELATIONSHIP_ATTRS = (qn("r:embed"), qn("r:link"), qn("r:id"), qn("r:pict"))


def slide_index(prs, slide) -> int:
    return list(prs.slides).index(slide)


def move_slide_before(prs, slide, before_slide) -> int:
    """Move ``slide`` to sit immediately before ``before_slide``; return new index."""
    target = slide_index(prs, before_slide)
    source = slide_index(prs, slide)
    if source < target:
        target -= 1
    move_slide(prs, slide, target)
    return target


def move_slide(prs, slide, new_index: int) -> None:
    sld_id_lst = prs.slides._sldIdLst
    sld_id = next(s for s in sld_id_lst if s.id == slide.slide_id)
    sld_id_lst.remove(sld_id)
    sld_id_lst.insert(new_index, sld_id)


def remove_slide(prs, slide) -> None:
    sld_id_lst = prs.slides._sldIdLst
    sld_id = next(s for s in sld_id_lst if s.id == slide.slide_id)
    prs.part.drop_rel(sld_id.rId)
    sld_id_lst.remove(sld_id)


def _remap_relationships(element, src_part, dst_part) -> None:
    for node in element.iter(etree.Element):
        for attr in _RELATIONSHIP_ATTRS:
            r_id = node.get(attr)
            if not r_id:
                continue
            rel = src_part.rels[r_id]
            if rel.is_external:
                new_r_id = dst_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
            else:
                new_r_id = dst_part.relate_to(rel.target_part, rel.reltype)
            node.set(attr, new_r_id)


def _blank_layout(prs):
    for layout in prs.slide_layouts:
        if "blank" in (layout.name or "").lower():
            return layout
    return prs.slide_layouts[0]


def import_slide_from_presentation(
    dst_prs,
    src_prs,
    src_slide_index: int,
    *,
    insert_index: int | None = None,
) -> object:
    """
    Copy a slide from another deck into ``dst_prs``.

    Uses a layout from the destination deck only (never the source slide layout),
    so parts from the source file are not merged into the output package.
    """
    source = src_prs.slides[src_slide_index]
    new_slide = dst_prs.slides.add_slide(_blank_layout(dst_prs))
    sp_tree = new_slide.shapes._spTree
    for shape in list(new_slide.shapes):
        sp_tree.remove(shape._element)

    source_bg = source._element.cSld.bg
    if source_bg is not None:
        bg = deepcopy(source_bg)
        _remap_relationships(bg, source.part, new_slide.part)
        new_slide._element.cSld.insert(0, bg)

    for shape in source.shapes:
        element = deepcopy(shape._element)
        _remap_relationships(element, source.part, new_slide.part)
        sp_tree.insert_element_before(element, "p:extLst")

    if insert_index is not None:
        move_slide(dst_prs, new_slide, insert_index)
    return new_slide


def duplicate_slide(prs, source, *, skip_shape_ids: frozenset[int] = frozenset()):
    """Append a copy of ``source`` (same layout, background and shapes) to the deck."""
    new_slide = prs.slides.add_slide(source.slide_layout)
    sp_tree = new_slide.shapes._spTree
    for shape in list(new_slide.shapes):
        sp_tree.remove(shape._element)

    source_bg = source._element.cSld.bg
    if source_bg is not None:
        bg = deepcopy(source_bg)
        _remap_relationships(bg, source.part, new_slide.part)
        new_slide._element.cSld.insert(0, bg)

    for shape in source.shapes:
        if shape.shape_id in skip_shape_ids:
            continue
        element = deepcopy(shape._element)
        _remap_relationships(element, source.part, new_slide.part)
        sp_tree.insert_element_before(element, "p:extLst")
    return new_slide
