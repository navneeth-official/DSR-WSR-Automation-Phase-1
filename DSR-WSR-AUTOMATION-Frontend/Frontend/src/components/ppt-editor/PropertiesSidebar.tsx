import type { SlideElement, TextElement } from "./types";
import type { UsePresentationEditorResult } from "./usePresentationEditor";

interface PropertiesSidebarProps {
  editor: UsePresentationEditorResult;
}

export function PropertiesSidebar({ editor }: PropertiesSidebarProps) {
  const element = editor.selectedElements[0] ?? null;

  if (!element) {
    return (
      <div className="w-64 flex-shrink-0 bg-white border-l border-gray-200 p-4">
        <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Properties</p>
        <p className="text-xs text-gray-400 mt-3">Select an object on the slide to edit its properties.</p>
        {editor.activeSlide && (
          <div className="mt-6 space-y-2">
            <p className="text-xs font-semibold text-gray-600">Slide</p>
            <label className="block text-xs text-gray-500">
              Title
              <input
                className="mt-1 w-full border border-gray-200 rounded px-2 py-1 text-xs"
                value={editor.activeSlide.title}
                onChange={(e) => {
                  if (!editor.document) return;
                  const slides = editor.document.slides.map((s, i) =>
                    i === editor.activeSlideIndex ? { ...s, title: e.target.value } : s,
                  );
                  editor.setDocument({ ...editor.document, slides });
                }}
              />
            </label>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="w-64 flex-shrink-0 bg-white border-l border-gray-200 p-4 overflow-y-auto">
      <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">Properties</p>
      <p className="text-xs text-brand-red font-medium mt-1 capitalize">{element.type}</p>

      <div className="mt-4 space-y-3">
        <NumberField label="X" value={element.x} onChange={(v) => editor.updateElement(element.id, { x: v })} />
        <NumberField label="Y" value={element.y} onChange={(v) => editor.updateElement(element.id, { y: v })} />
        <NumberField
          label="Width"
          value={element.width}
          onChange={(v) => editor.updateElement(element.id, { width: v })}
        />
        <NumberField
          label="Height"
          value={element.height}
          onChange={(v) => editor.updateElement(element.id, { height: v })}
        />
        <NumberField
          label="Rotation"
          value={element.rotation}
          onChange={(v) => editor.updateElement(element.id, { rotation: v })}
        />
      </div>

      {element.type === "text" && <TextProperties element={element} editor={editor} />}
      {element.type === "shape" && (
        <div className="mt-4 space-y-2">
          <label className="block text-xs text-gray-500">
            Fill
            <input
              type="color"
              className="mt-1 w-full h-8 border border-gray-200 rounded"
              value={element.fill}
              onChange={(e) => editor.updateElement(element.id, { fill: e.target.value })}
            />
          </label>
          <label className="block text-xs text-gray-500">
            Stroke
            <input
              type="color"
              className="mt-1 w-full h-8 border border-gray-200 rounded"
              value={element.stroke}
              onChange={(e) => editor.updateElement(element.id, { stroke: e.target.value })}
            />
          </label>
        </div>
      )}

      <button
        type="button"
        className="mt-6 w-full text-xs font-semibold text-red-600 border border-red-200 rounded py-1.5 hover:bg-red-50"
        onClick={editor.deleteSelected}
      >
        Delete object
      </button>
    </div>
  );
}

function TextProperties({
  element,
  editor,
}: {
  element: TextElement;
  editor: UsePresentationEditorResult;
}) {
  return (
    <div className="mt-4 space-y-2">
      <label className="block text-xs text-gray-500">
        Font size
        <input
          type="number"
          className="mt-1 w-full border border-gray-200 rounded px-2 py-1 text-xs"
          value={element.style.fontSize}
          onChange={(e) =>
            editor.updateElement(element.id, {
              style: { ...element.style, fontSize: Number(e.target.value) || 12 },
            } as Partial<SlideElement>)
          }
        />
      </label>
      <label className="block text-xs text-gray-500">
        Color
        <input
          type="color"
          className="mt-1 w-full h-8 border border-gray-200 rounded"
          value={element.style.color}
          onChange={(e) =>
            editor.updateElement(element.id, {
              style: { ...element.style, color: e.target.value },
            } as Partial<SlideElement>)
          }
        />
      </label>
      <label className="flex items-center gap-2 text-xs text-gray-600">
        <input
          type="checkbox"
          checked={element.style.bold}
          onChange={(e) =>
            editor.updateElement(element.id, {
              style: { ...element.style, bold: e.target.checked },
            } as Partial<SlideElement>)
          }
        />
        Bold
      </label>
      <label className="flex items-center gap-2 text-xs text-gray-600">
        <input
          type="checkbox"
          checked={element.style.italic}
          onChange={(e) =>
            editor.updateElement(element.id, {
              style: { ...element.style, italic: e.target.checked },
            } as Partial<SlideElement>)
          }
        />
        Italic
      </label>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-xs text-gray-500">
      {label}
      <input
        type="number"
        className="mt-1 w-full border border-gray-200 rounded px-2 py-1 text-xs"
        value={Math.round(value)}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
      />
    </label>
  );
}
