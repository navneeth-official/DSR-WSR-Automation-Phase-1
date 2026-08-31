import type { SlideElement, TextElement } from "./types";
import type { UsePresentationEditorResult } from "./usePresentationEditor";

interface PropertiesBarProps {
  editor: UsePresentationEditorResult;
}

export function PropertiesBar({ editor }: PropertiesBarProps) {
  const element = editor.selectedElements[0] ?? null;

  if (!element) {
    return (
      <div className="flex items-center gap-4 px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-400 min-h-[40px]">
        <span>Edit directly on the slide · Drag to move · Changes save to the .pptx automatically</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-gray-50 border-b border-gray-200 flex-wrap min-h-[40px]">
      <span className="text-xs font-semibold text-brand-red capitalize">{element.type}</span>

      <NumberField label="X" value={element.x} onChange={(v) => editor.updateElement(element.id, { x: v })} />
      <NumberField label="Y" value={element.y} onChange={(v) => editor.updateElement(element.id, { y: v })} />
      <NumberField
        label="W"
        value={element.width}
        onChange={(v) => editor.updateElement(element.id, { width: v })}
      />
      <NumberField
        label="H"
        value={element.height}
        onChange={(v) => editor.updateElement(element.id, { height: v })}
      />
      <NumberField
        label="°"
        value={element.rotation}
        onChange={(v) => editor.updateElement(element.id, { rotation: v })}
      />

      {element.type === "text" && <TextFields element={element} editor={editor} />}

      {element.type === "shape" && (
        <>
          <label className="flex items-center gap-1 text-xs text-gray-500">
            Fill
            <input
              type="color"
              className="w-7 h-7 border border-gray-200 rounded cursor-pointer"
              value={element.fill}
              onChange={(e) => editor.updateElement(element.id, { fill: e.target.value })}
            />
          </label>
          <label className="flex items-center gap-1 text-xs text-gray-500">
            Stroke
            <input
              type="color"
              className="w-7 h-7 border border-gray-200 rounded cursor-pointer"
              value={element.stroke}
              onChange={(e) => editor.updateElement(element.id, { stroke: e.target.value })}
            />
          </label>
        </>
      )}

      <button
        type="button"
        className="ml-auto text-xs font-semibold text-red-600 hover:underline"
        onClick={editor.deleteSelected}
      >
        Delete
      </button>
    </div>
  );
}

function TextFields({
  element,
  editor,
}: {
  element: TextElement;
  editor: UsePresentationEditorResult;
}) {
  return (
    <>
      <label className="flex items-center gap-1 text-xs text-gray-500">
        Size
        <input
          type="number"
          className="w-14 border border-gray-200 rounded px-1.5 py-0.5 text-xs"
          value={element.style.fontSize}
          onChange={(e) =>
            editor.updateElement(element.id, {
              style: { ...element.style, fontSize: Number(e.target.value) || 12 },
            } as Partial<SlideElement>)
          }
        />
      </label>
      <label className="flex items-center gap-1 text-xs text-gray-500">
        Color
        <input
          type="color"
          className="w-7 h-7 border border-gray-200 rounded cursor-pointer"
          value={element.style.color}
          onChange={(e) =>
            editor.updateElement(element.id, {
              style: { ...element.style, color: e.target.value },
            } as Partial<SlideElement>)
          }
        />
      </label>
      <label className="flex items-center gap-1 text-xs text-gray-600">
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
      <label className="flex items-center gap-1 text-xs text-gray-600">
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
    </>
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
    <label className="flex items-center gap-1 text-xs text-gray-500">
      {label}
      <input
        type="number"
        className="w-14 border border-gray-200 rounded px-1.5 py-0.5 text-xs"
        value={Math.round(value)}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
      />
    </label>
  );
}
