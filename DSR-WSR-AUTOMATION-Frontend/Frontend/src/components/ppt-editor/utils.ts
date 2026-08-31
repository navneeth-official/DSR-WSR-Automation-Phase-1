import type { PresentationDocument, SlideElement } from "./types";

export function cloneDocument(doc: PresentationDocument): PresentationDocument {
  return JSON.parse(JSON.stringify(doc)) as PresentationDocument;
}

export function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function slideNavLabel(title: string, slideIndex: number): string {
  const deliveryMatch = title.match(/Delivery status\s*[–-]\s*(.+)/i);
  if (deliveryMatch?.[1]) return deliveryMatch[1].trim();
  if (/index|track/i.test(title)) return title;
  return title.length > 40 ? `${title.slice(0, 37)}…` : title || `Slide ${slideIndex}`;
}

export function isInteractiveElement(el: SlideElement): boolean {
  if (el.locked) return false;
  if (el.type === "shape" && el.isTableCell) return false;
  return true;
}

export function hasElementMoved(el: SlideElement): boolean {
  if (el.originalX === undefined || el.originalY === undefined) return false;
  const dw = el.originalWidth !== undefined ? Math.abs(el.width - el.originalWidth) : 0;
  const dh = el.originalHeight !== undefined ? Math.abs(el.height - el.originalHeight) : 0;
  return (
    Math.abs(el.x - el.originalX) > 0.5 ||
    Math.abs(el.y - el.originalY) > 0.5 ||
    dw > 0.5 ||
    dh > 0.5
  );
}

export function mergePreviewIntoDocument(
  doc: PresentationDocument,
  previewSlides: { slide_index: number; image_url: string }[],
): PresentationDocument {
  const byIndex = Object.fromEntries(previewSlides.map((p) => [p.slide_index, p.image_url]));
  const version = Date.now();
  return {
    ...doc,
    slides: doc.slides.map((slide) => ({
      ...slide,
      backgroundImage: byIndex[slide.index]
        ? `${byIndex[slide.index]}${byIndex[slide.index].includes("?") ? "&" : "?"}v=${version}`
        : slide.backgroundImage,
      elements: slide.elements.map((el) => ({
        ...el,
        originalX: el.x,
        originalY: el.y,
        originalWidth: el.width,
        originalHeight: el.height,
        ...(el.type === "text" ? { isDirty: false, originalText: el.text } : {}),
      })),
    })),
  };
}
