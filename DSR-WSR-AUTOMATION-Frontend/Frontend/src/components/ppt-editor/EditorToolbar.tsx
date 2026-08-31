import { useRef } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  FolderOpen,
  ImagePlus,
  Redo2,
  Save,
  Shapes,
  SquarePlus,
  Type,
  Undo2,
  Upload,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { EditorSlide } from "./types";
import type { UsePresentationEditorResult } from "./usePresentationEditor";

function navLabel(title: string, slideIndex: number): string {
  const deliveryMatch = title.match(/Delivery status\s*[–-]\s*(.+)/i);
  if (deliveryMatch?.[1]) return deliveryMatch[1].trim();
  if (/index|track/i.test(title)) return title;
  return title.length > 40 ? `${title.slice(0, 37)}…` : title || `Slide ${slideIndex}`;
}

interface EditorToolbarProps {
  editor: UsePresentationEditorResult;
  slides: EditorSlide[];
  filename: string;
  saveMessage?: string;
  onOpen: () => void;
  onSave: () => void;
  onExport: () => void;
  saving?: boolean;
  exporting?: boolean;
}

export function EditorToolbar({
  editor,
  slides,
  filename,
  saveMessage,
  onOpen,
  onSave,
  onExport,
  saving,
  exporting,
}: EditorToolbarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeSlide = slides[editor.activeSlideIndex];

  return (
    <div className="flex flex-col bg-white border-b border-gray-200">
      <div className="flex items-center gap-1 px-3 py-2 flex-wrap">
        <ToolbarButton label="Reload" icon={<FolderOpen className="w-3.5 h-3.5" />} onClick={onOpen} />
        <ToolbarButton
          label="Save"
          icon={<Save className="w-3.5 h-3.5" />}
          onClick={onSave}
          disabled={saving}
        />
        <ToolbarButton
          label="Export PPT"
          icon={<Upload className="w-3.5 h-3.5" />}
          onClick={onExport}
          disabled={exporting}
        />
        <Divider />
        <ToolbarButton
          label="Undo"
          icon={<Undo2 className="w-3.5 h-3.5" />}
          onClick={editor.undo}
          disabled={!editor.canUndo}
        />
        <ToolbarButton
          label="Redo"
          icon={<Redo2 className="w-3.5 h-3.5" />}
          onClick={editor.redo}
          disabled={!editor.canRedo}
        />
        <Divider />
        <ToolbarButton
          label="Zoom out"
          icon={<ZoomOut className="w-3.5 h-3.5" />}
          onClick={() => editor.setZoom(Math.max(0.5, editor.zoom - 0.05))}
        />
        <span className="text-xs text-gray-500 w-10 text-center">{Math.round(editor.zoom * 100)}%</span>
        <ToolbarButton
          label="Zoom in"
          icon={<ZoomIn className="w-3.5 h-3.5" />}
          onClick={() => editor.setZoom(Math.min(1.2, editor.zoom + 0.05))}
        />
        <ToolbarButton label="Fit" onClick={() => editor.fitToView?.()} />
        <Divider />
        <ToolbarButton label="Add slide" icon={<SquarePlus className="w-3.5 h-3.5" />} onClick={editor.addSlide} />
        <ToolbarButton label="Text" icon={<Type className="w-3.5 h-3.5" />} onClick={editor.addTextBox} />
        <ToolbarButton label="Shape" icon={<Shapes className="w-3.5 h-3.5" />} onClick={editor.addShape} />
        <ToolbarButton
          label="Image"
          icon={<ImagePlus className="w-3.5 h-3.5" />}
          onClick={() => fileInputRef.current?.click()}
        />
        <ToolbarButton
          label="Duplicate"
          icon={<Copy className="w-3.5 h-3.5" />}
          onClick={editor.duplicateSelected}
          disabled={!editor.selectedIds.length}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void editor.addImageFromFile(file);
            e.target.value = "";
          }}
        />
        {saveMessage && (
          <span className="ml-auto text-xs text-gray-500 truncate max-w-[200px]">{saveMessage}</span>
        )}
      </div>

      <div className="flex items-center gap-2 px-3 py-1.5 border-t border-gray-100 bg-gray-50/80 flex-wrap">
        <button
          type="button"
          onClick={() => editor.setActiveSlideIndex(Math.max(0, editor.activeSlideIndex - 1))}
          disabled={editor.activeSlideIndex === 0}
          className="p-1 rounded border border-gray-200 hover:bg-white disabled:opacity-40"
          title="Previous slide"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        <select
          className="text-xs border border-gray-200 rounded-md px-2 py-1 bg-white max-w-[280px] min-w-[180px]"
          value={editor.activeSlideIndex}
          onChange={(e) => editor.setActiveSlideIndex(Number(e.target.value))}
        >
          {slides.map((slide, idx) => (
            <option key={slide.id} value={idx}>
              {String(slide.index).padStart(2, "0")} — {navLabel(slide.title, slide.index)}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={() =>
            editor.setActiveSlideIndex(Math.min(slides.length - 1, editor.activeSlideIndex + 1))
          }
          disabled={editor.activeSlideIndex >= slides.length - 1}
          className="p-1 rounded border border-gray-200 hover:bg-white disabled:opacity-40"
          title="Next slide"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        <span className="text-xs text-gray-500">
          {editor.activeSlideIndex + 1} / {slides.length}
        </span>

        <span className="text-xs text-gray-400 truncate hidden sm:inline" title={filename}>
          {filename}
        </span>

        {activeSlide && (
          <span className="text-xs text-gray-600 font-medium truncate ml-auto hidden md:inline" title={activeSlide.title}>
            {activeSlide.title}
          </span>
        )}

        <button
          type="button"
          onClick={editor.duplicateSlide}
          className="text-[10px] font-semibold border border-gray-200 rounded px-2 py-0.5 hover:bg-white ml-1"
        >
          Dup slide
        </button>
        <button
          type="button"
          onClick={editor.deleteSlide}
          disabled={slides.length <= 1}
          className="text-[10px] font-semibold border border-gray-200 rounded px-2 py-0.5 hover:bg-white disabled:opacity-40"
        >
          Del slide
        </button>
      </div>
    </div>
  );
}

function ToolbarButton({
  label,
  icon,
  onClick,
  disabled,
}: {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium border border-gray-200 rounded-md hover:bg-gray-50 disabled:opacity-40"
    >
      {icon}
      <span className="hidden xl:inline">{label}</span>
    </button>
  );
}

function Divider() {
  return <div className="w-px h-6 bg-gray-200 mx-1" />;
}
