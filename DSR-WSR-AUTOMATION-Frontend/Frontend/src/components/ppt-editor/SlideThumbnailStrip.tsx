import { useEffect, useRef } from "react";
import type { EditorSlide } from "./types";
import { slideNavLabel } from "./utils";

interface SlideThumbnailStripProps {
  slides: EditorSlide[];
  activeIndex: number;
  onSelect: (index: number) => void;
}

export function SlideThumbnailStrip({
  slides,
  activeIndex,
  onSelect,
}: SlideThumbnailStripProps) {
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIndex]);

  return (
    <aside className="w-[212px] flex-shrink-0 bg-[#eceff1] border-r border-gray-300 flex flex-col min-h-0">
      <div className="px-3 py-2.5 border-b border-gray-300 bg-white">
        <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">
          Slides
        </p>
        <p className="text-[10px] text-gray-400 mt-0.5">{slides.length} total</p>
      </div>

      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-2.5">
        {slides.map((slide, idx) => {
          const isActive = idx === activeIndex;
          return (
            <button
              key={slide.id}
              ref={isActive ? activeRef : undefined}
              type="button"
              onClick={() => onSelect(idx)}
              title={slide.title}
              className={`w-full text-left rounded transition-all outline-none ${
                isActive
                  ? "ring-2 ring-brand-red ring-offset-2 ring-offset-[#eceff1]"
                  : "hover:ring-1 hover:ring-gray-400"
              }`}
            >
              <div className="relative aspect-video bg-white rounded-sm overflow-hidden shadow border border-gray-300/80">
                {slide.backgroundImage ? (
                  <img
                    src={slide.backgroundImage}
                    alt=""
                    className="w-full h-full object-cover pointer-events-none"
                    loading="lazy"
                    draggable={false}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 px-2">
                    <span className="text-[9px] text-gray-400 text-center leading-tight">
                      {slideNavLabel(slide.title, slide.index)}
                    </span>
                  </div>
                )}
                <span className="absolute bottom-1 left-1 min-w-[18px] px-1 py-px text-[9px] font-bold leading-none text-center bg-black/65 text-white rounded-sm">
                  {slide.index}
                </span>
              </div>
              <p
                className={`mt-1.5 text-[10px] leading-snug line-clamp-2 px-0.5 ${
                  isActive ? "text-brand-red font-semibold" : "text-gray-600"
                }`}
              >
                {slideNavLabel(slide.title, slide.index)}
              </p>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
