import { useCallback, useEffect, useRef, useState } from "react";
import type { EditorSlide, SlideElement, TextElement } from "./types";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "./types";
import { hasElementMoved, isInteractiveElement } from "./utils";

interface SlideCanvasProps {
  slide: EditorSlide;
  zoom: number;
  selectedIds: string[];
  onSelect: (ids: string[]) => void;
  onClearSelection: () => void;
  onUpdateElement: (
    id: string,
    patch: Partial<SlideElement>,
    options?: { history?: boolean },
  ) => void;
  onCommit?: () => void;
}

type DragMode = "move" | "resize-se" | null;

function normalizeFontFamily(fontFamily: string): string {
  if (!fontFamily || fontFamily.startsWith("+")) {
    return "Calibri, Arial, sans-serif";
  }
  return fontFamily;
}

function textStyle(element: TextElement, showGlyphs: boolean): React.CSSProperties {
  return {
    fontSize: element.style.fontSize,
    fontFamily: normalizeFontFamily(element.style.fontFamily),
    color: showGlyphs ? element.style.color : "transparent",
    fontWeight: element.style.bold ? "bold" : "normal",
    fontStyle: element.style.italic ? "italic" : "normal",
    textAlign: element.style.align,
    lineHeight: 1.25,
    background: "transparent",
    caretColor: element.style.color,
  };
}

export function SlideCanvas({
  slide,
  zoom,
  selectedIds,
  onSelect,
  onClearSelection,
  onUpdateElement,
  onCommit,
}: SlideCanvasProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const editRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    id: string;
    mode: DragMode;
    startX: number;
    startY: number;
    orig: SlideElement;
    moved: boolean;
  } | null>(null);

  const usePptPreview = Boolean(slide.backgroundImage);
  const interactiveElements = slide.elements.filter(isInteractiveElement);

  useEffect(() => {
    setEditingId(null);
  }, [slide.id]);

  useEffect(() => {
    if (editingId && editRef.current) {
      const el = slide.elements.find((e) => e.id === editingId);
      if (el?.type === "text") {
        editRef.current.innerText = el.text;
        editRef.current.focus();
      }
    }
  }, [editingId, slide.elements]);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent, element: SlideElement, mode: DragMode = "move") => {
      if (!isInteractiveElement(element)) return;
      if (mode === "move" && element.type === "text" && element.positionLocked) return;
      if (editingId && editingId !== element.id) return;
      e.stopPropagation();
      onSelect([element.id]);
      dragRef.current = {
        id: element.id,
        mode,
        startX: e.clientX,
        startY: e.clientY,
        orig: element,
        moved: false,
      };
      setDraggingId(element.id);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [onSelect, editingId],
  );

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const dx = (e.clientX - drag.startX) / zoom;
      const dy = (e.clientY - drag.startY) / zoom;
      const orig = drag.orig;
      drag.moved = true;
      if (drag.mode === "move") {
        onUpdateElement(
          drag.id,
          { x: orig.x + dx, y: orig.y + dy },
          { history: false },
        );
      } else if (drag.mode === "resize-se") {
        onUpdateElement(
          drag.id,
          {
            width: Math.max(24, orig.width + dx),
            height: Math.max(24, orig.height + dy),
          },
          { history: false },
        );
      }
    };
    const onUp = () => {
      const drag = dragRef.current;
      if (drag?.moved) {
        onUpdateElement(drag.id, {}, { history: true });
        onCommit?.();
      }
      dragRef.current = null;
      setDraggingId(null);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [onUpdateElement, onCommit, zoom]);

  const renderElementVisual = (element: SlideElement, selected: boolean, editing: boolean) => {
    const moved = hasElementMoved(element);
    const dragging = draggingId === element.id;
    const showOverlay = selected || editing || dragging || moved;

    if (element.type === "image") {
      if (!usePptPreview || showOverlay) {
        return (
          <img
            src={element.src}
            alt=""
            className="w-full h-full object-fill pointer-events-none select-none"
            style={{ opacity: dragging ? 0.85 : 1 }}
            draggable={false}
          />
        );
      }
      return null;
    }

    if (element.type === "shape") {
      if (!usePptPreview || showOverlay) {
        return (
          <div
            className="w-full h-full pointer-events-none"
            style={{
              background: element.fill,
              border: `${element.strokeWidth}px solid ${element.stroke}`,
              opacity: dragging ? 0.85 : 1,
            }}
          />
        );
      }
      return null;
    }

    const showGlyphs = !usePptPreview || editing || Boolean(element.isDirty);

    if (editing) {
      return (
        <div
          ref={editRef}
          className="w-full h-full overflow-auto outline-none px-0.5 py-0"
          style={textStyle(element, true)}
          contentEditable
          suppressContentEditableWarning
          onInput={(e) =>
            onUpdateElement(
              element.id,
              { text: e.currentTarget.innerText, isDirty: true },
              { history: false },
            )
          }
          onBlur={() => {
            onUpdateElement(element.id, { isDirty: true }, { history: true });
            setEditingId(null);
            onCommit?.();
          }}
          onPointerDown={(e) => e.stopPropagation()}
        />
      );
    }

    return (
      <div
        className="w-full h-full whitespace-pre-wrap overflow-hidden px-0.5 py-0 pointer-events-none"
        style={textStyle(element, showGlyphs)}
      >
        {showGlyphs || !usePptPreview ? element.text : "\u00a0"}
      </div>
    );
  };

  return (
    <div
      className="relative bg-gray-900 shadow-2xl overflow-hidden"
      style={{
        width: CANVAS_WIDTH * zoom,
        height: CANVAS_HEIGHT * zoom,
      }}
      onPointerDown={() => {
        if (editingId) return;
        onClearSelection();
        setEditingId(null);
      }}
    >
      <div
        className="relative origin-top-left"
        style={{
          width: CANVAS_WIDTH,
          height: CANVAS_HEIGHT,
          transform: `scale(${zoom})`,
          background: slide.background,
        }}
      >
        {slide.backgroundImage && (
          <img
            src={slide.backgroundImage}
            alt=""
            className="absolute inset-0 w-full h-full object-fill pointer-events-none select-none"
            draggable={false}
          />
        )}

        {interactiveElements.map((element) => {
          const selected = selectedIds.includes(element.id);
          const editing = editingId === element.id;
          const canMove = !(element.type === "text" && element.positionLocked);
          const moved = hasElementMoved(element);
          const showOutline = selected || editing || draggingId === element.id;

          return (
            <div
              key={element.id}
              style={{
                position: "absolute",
                left: element.x,
                top: element.y,
                width: element.width,
                height: element.height,
                transform: `rotate(${element.rotation}deg)`,
                transformOrigin: "center center",
                boxSizing: "border-box",
                zIndex: showOutline ? 50 : 10,
                cursor: editing
                  ? "text"
                  : canMove
                    ? "move"
                    : "text",
                background: "transparent",
                outline: showOutline ? "2px dashed #6366f1" : "none",
                outlineOffset: 0,
              }}
              className={
                !showOutline && usePptPreview ? "hover:outline hover:outline-1 hover:outline-brand-red/40" : ""
              }
              onPointerDown={(e) => handlePointerDown(e, element, "move")}
              onDoubleClick={(e) => {
                if (element.type !== "text") return;
                e.stopPropagation();
                setEditingId(element.id);
                onSelect([element.id]);
              }}
            >
              {renderElementVisual(element, selected, editing)}
              {selected && canMove && !editing && (
                <div
                  className="absolute -bottom-1 -right-1 w-3 h-3 bg-brand-orange rounded-sm cursor-se-resize z-10"
                  onPointerDown={(e) => handlePointerDown(e, element, "resize-se")}
                />
              )}
            </div>
          );
        })}

        {!slide.backgroundImage && interactiveElements.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-gray-400">
            Slide preview unavailable — reload or regenerate the deck
          </div>
        )}
      </div>
    </div>
  );
}
