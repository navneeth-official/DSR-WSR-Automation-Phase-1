import { useEffect, useMemo, useRef, useState } from "react";
import type { WsrPreviewSlide } from "@/api/wsr";

function navLabel(title: string, slideIndex: number): string {
  const deliveryMatch = title.match(/Delivery status\s*[–-]\s*(.+)/i);
  if (deliveryMatch?.[1]) {
    return deliveryMatch[1].trim();
  }
  if (/index|track/i.test(title)) {
    return title;
  }
  return title.length > 48 ? `${title.slice(0, 45)}…` : title || `Slide ${slideIndex}`;
}

interface WSRPptViewerProps {
  previewSlides: WsrPreviewSlide[];
  filename: string;
  /** When false, scroll through all slides without the left thumbnail rail. */
  showSlideThumbnails?: boolean;
}

export function WSRPptViewer({
  previewSlides,
  filename,
  showSlideThumbnails = true,
}: WSRPptViewerProps) {
  const slides = useMemo(
    () => [...previewSlides].sort((a, b) => a.slide_index - b.slide_index),
    [previewSlides],
  );
  const [activeIndex, setActiveIndex] = useState(0);
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setActiveIndex(0);
  }, [previewSlides]);

  useEffect(() => {
    if (!showSlideThumbnails) return;
    activeRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIndex, showSlideThumbnails]);

  useEffect(() => {
    if (!showSlideThumbnails) return;
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }
      if (e.key === "ArrowLeft") {
        setActiveIndex((i) => Math.max(0, i - 1));
      } else if (e.key === "ArrowRight") {
        setActiveIndex((i) => Math.min(slides.length - 1, i + 1));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [slides.length, showSlideThumbnails]);

  if (slides.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-500 px-6 text-center">
        Slide previews are not available. Download the PPT to view the generated deck.
      </div>
    );
  }

  const current = slides[activeIndex] ?? slides[0];

  if (!showSlideThumbnails) {
    return (
      <div className="flex flex-col h-full min-h-0 bg-gray-200">
        <div className="px-4 py-2 bg-white border-b border-gray-200 flex-shrink-0">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Preview</p>
          <p className="text-xs text-gray-600 truncate mt-0.5" title={filename}>
            {filename}
          </p>
          <p className="text-[10px] text-gray-400 mt-0.5">{slides.length} slides · scroll to browse</p>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0 p-4 space-y-5">
          {slides.map((slide) => (
            <div
              key={slide.slide_index}
              className="bg-white shadow-lg rounded overflow-hidden w-full max-w-5xl mx-auto"
            >
              <div className="px-3 py-1.5 bg-gray-50 border-b border-gray-100 flex items-center gap-2 min-w-0">
                <span className="text-[10px] font-bold text-gray-400 flex-shrink-0">
                  {slide.slide_index} / {slides.length}
                </span>
                <span className="text-[10px] text-gray-600 truncate" title={slide.title}>
                  {slide.title || `Slide ${slide.slide_index}`}
                </span>
              </div>
              <img
                src={slide.image_url}
                alt={slide.title || `Slide ${slide.slide_index}`}
                className="w-full h-auto block"
                loading="lazy"
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <div className="w-[212px] flex-shrink-0 bg-[#eceff1] border-r border-gray-300 flex flex-col min-h-0">
        <div className="px-3 py-2.5 border-b border-gray-300 bg-white">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Slides</p>
          <p className="text-[10px] text-gray-400 mt-0.5 truncate" title={filename}>
            {filename}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto py-2 px-2 space-y-2.5">
          {slides.map((slide, idx) => (
            <button
              key={slide.slide_index}
              ref={activeIndex === idx ? activeRef : undefined}
              type="button"
              onClick={() => setActiveIndex(idx)}
              title={slide.title}
              className={`w-full text-left rounded transition-all outline-none ${
                activeIndex === idx
                  ? "ring-2 ring-brand-red ring-offset-2 ring-offset-[#eceff1]"
                  : "hover:ring-1 hover:ring-gray-400"
              }`}
            >
              <div className="relative aspect-video bg-white rounded-sm overflow-hidden shadow border border-gray-300/80">
                <img
                  src={slide.image_url}
                  alt=""
                  className="w-full h-full object-contain pointer-events-none"
                  loading="lazy"
                  draggable={false}
                />
                <span className="absolute bottom-1 left-1 min-w-[18px] px-1 py-px text-[9px] font-bold leading-none text-center bg-black/65 text-white rounded-sm">
                  {slide.slide_index}
                </span>
              </div>
              <p
                className={`mt-1.5 text-[10px] leading-snug line-clamp-2 px-0.5 ${
                  activeIndex === idx ? "text-brand-red font-semibold" : "text-gray-600"
                }`}
              >
                {navLabel(slide.title, slide.slide_index)}
              </p>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0 min-h-0 bg-gray-200 overflow-hidden">
        <div className="flex-1 min-h-0 flex items-start justify-center overflow-y-auto p-4">
          <div className="bg-white shadow-2xl rounded overflow-hidden w-full max-w-5xl">
            <img
              key={current.image_url}
              src={current.image_url}
              alt={current.title || `Slide ${current.slide_index}`}
              className="w-full h-auto block"
            />
          </div>
        </div>

        <div className="px-4 py-2 bg-white border-t border-gray-200 flex items-center gap-2 min-w-0">
          <span className="text-xs font-bold text-gray-400 flex-shrink-0">
            {activeIndex + 1} / {slides.length}
          </span>
          <span className="text-xs text-gray-400 flex-shrink-0">·</span>
          <span className="text-xs font-bold text-gray-400 flex-shrink-0">
            #{current.slide_index}
          </span>
          <span className="text-xs text-gray-600 font-medium truncate" title={current.title}>
            {current.title}
          </span>
        </div>
      </div>
    </div>
  );
}
