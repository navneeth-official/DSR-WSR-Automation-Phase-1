import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  exportEditorDeck,
  fetchEditorDeck,
  saveEditorDeck,
  syncEditorDeck,
} from "@/api/wsr";
import { EditorToolbar } from "./EditorToolbar";
import { PropertiesBar } from "./PropertiesBar";
import { SlideCanvas } from "./SlideCanvas";
import { SlideThumbnailStrip } from "./SlideThumbnailStrip";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "./types";
import { usePresentationEditor } from "./usePresentationEditor";
import { mergePreviewIntoDocument } from "./utils";

interface WSRPptEditorProps {
  startDate: string;
  endDate: string;
  filename: string;
}

export function WSRPptEditor({ startDate, endDate, filename }: WSRPptEditorProps) {
  const editor = usePresentationEditor();
  const setDocumentRef = useRef(editor.setDocument);
  const replaceDocumentRef = useRef(editor.replaceDocument);
  setDocumentRef.current = editor.setDocument;
  replaceDocumentRef.current = editor.replaceDocument;

  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const documentRef = useRef(editor.document);
  documentRef.current = editor.document;
  const syncTimerRef = useRef<number | null>(null);
  const syncingRef = useRef(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  const fitToView = useCallback(() => {
    const container = canvasContainerRef.current;
    if (!container) return;
    const paddingX = 32;
    const paddingY = 24;
    const availableWidth = Math.max(0, container.clientWidth - paddingX);
    const availableHeight = Math.max(0, container.clientHeight - paddingY);
    if (availableWidth === 0 || availableHeight === 0) return;

    const scaleX = availableWidth / CANVAS_WIDTH;
    const scaleY = availableHeight / CANVAS_HEIGHT;
    // Floor scale so the slide never overflows the viewport
    const scale = Math.min(scaleX, scaleY, 1);
    const zoom = Math.max(0.35, Math.floor(scale * 1000) / 1000);
    editor.setZoom(zoom);
  }, [editor]);

  const loadDeck = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const doc = await fetchEditorDeck(startDate, endDate);
      const cacheBust = Date.now();
      doc.slides = doc.slides.map((slide) => ({
        ...slide,
        backgroundImage: slide.backgroundImage
          ? `${slide.backgroundImage}${slide.backgroundImage.includes("?") ? "&" : "?"}v=${cacheBust}`
          : null,
      }));
      setDocumentRef.current(doc);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load editor deck");
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  const scheduleSyncToPptx = useCallback(() => {
    if (syncTimerRef.current) {
      window.clearTimeout(syncTimerRef.current);
    }
    syncTimerRef.current = window.setTimeout(() => {
      void (async () => {
        const doc = documentRef.current;
        if (!doc || syncingRef.current) return;
        syncingRef.current = true;
        setSaveMessage("Updating PowerPoint…");
        try {
          const result = await syncEditorDeck(startDate, endDate, doc);
          const merged = mergePreviewIntoDocument(doc, result.preview_slides);
          replaceDocumentRef.current(merged);
          setSaveMessage("Updated");
          window.setTimeout(() => setSaveMessage(""), 1200);
        } catch (err) {
          setSaveMessage(err instanceof Error ? err.message : "Sync failed");
        } finally {
          syncingRef.current = false;
        }
      })();
    }, 700);
  }, [startDate, endDate]);

  useEffect(() => {
    void loadDeck();
  }, [loadDeck]);

  useEffect(() => {
    if (!editor.document || loading) return;
    const timer = window.setTimeout(fitToView, 50);
    return () => window.clearTimeout(timer);
  }, [editor.document, editor.activeSlideIndex, loading, fitToView]);

  useEffect(() => {
    const container = canvasContainerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => fitToView());
    observer.observe(container);
    return () => observer.disconnect();
  }, [fitToView, loading]);

  const handleSave = useCallback(async () => {
    if (!editor.document) return;
    setSaving(true);
    setSaveMessage("");
    try {
      await saveEditorDeck(startDate, endDate, editor.document);
      setSaveMessage("Saved");
      window.setTimeout(() => setSaveMessage(""), 2000);
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [editor.document, startDate, endDate]);

  const handleExport = useCallback(async () => {
    if (!editor.document) return;
    setExporting(true);
    try {
      const blob = await exportEditorDeck(startDate, endDate, editor.document);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = editor.document.filename || filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setSaveMessage("Exported — refreshing slide previews…");
      await loadDeck();
      setSaveMessage("Exported to .pptx");
      window.setTimeout(() => setSaveMessage(""), 2500);
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }, [editor.document, startDate, endDate, filename, loadDeck]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        editor.undo();
      } else if (mod && (e.key === "y" || (e.key === "z" && e.shiftKey))) {
        e.preventDefault();
        editor.redo();
      } else if (mod && e.key === "c") {
        e.preventDefault();
        editor.copySelected();
      } else if (mod && e.key === "v") {
        e.preventDefault();
        editor.pasteClipboard();
      } else if (mod && e.key === "d") {
        e.preventDefault();
        editor.duplicateSelected();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        editor.deleteSelected();
      } else if (e.key === "ArrowLeft" && editor.activeSlideIndex > 0) {
        editor.setActiveSlideIndex(editor.activeSlideIndex - 1);
      } else if (
        e.key === "ArrowRight" &&
        editor.document &&
        editor.activeSlideIndex < editor.document.slides.length - 1
      ) {
        editor.setActiveSlideIndex(editor.activeSlideIndex + 1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editor]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6">
        <Loader2 className="w-8 h-8 text-brand-red animate-spin mb-3" />
        <p className="text-sm text-gray-600">Loading presentation from .pptx…</p>
      </div>
    );
  }

  if (error || !editor.document) {
    return (
      <div className="max-w-lg mx-auto bg-red-50 border border-red-200 rounded-xl p-5 m-6">
        <p className="text-sm font-semibold text-red-700">Editor failed to load</p>
        <p className="text-xs text-red-600 mt-2">{error || "No document"}</p>
        <button
          type="button"
          onClick={() => void loadDeck()}
          className="mt-4 text-xs font-semibold text-red-700 underline"
        >
          Retry
        </button>
      </div>
    );
  }

  const editorWithFit = { ...editor, fitToView };

  return (
    <div className="flex flex-col h-full min-h-0">
      <EditorToolbar
        editor={editorWithFit}
        slides={editor.document.slides}
        filename={filename}
        saveMessage={saveMessage}
        onOpen={() => void loadDeck()}
        onSave={() => void handleSave()}
        onExport={() => void handleExport()}
        saving={saving}
        exporting={exporting}
      />

      <PropertiesBar editor={editor} />

      <div className="flex flex-1 min-h-0">
        <SlideThumbnailStrip
          slides={editor.document.slides}
          activeIndex={editor.activeSlideIndex}
          onSelect={editor.setActiveSlideIndex}
        />

        <div
          ref={canvasContainerRef}
          className="flex-1 min-h-0 bg-gray-200 flex items-start justify-center overflow-auto pt-2 px-4 pb-4"
        >
          {editor.activeSlide && (
            <SlideCanvas
              slide={editor.activeSlide}
              zoom={editor.zoom}
              selectedIds={editor.selectedIds}
              onSelect={editor.selectElements}
              onClearSelection={editor.clearSelection}
              onUpdateElement={editor.updateElement}
              onCommit={scheduleSyncToPptx}
            />
          )}
        </div>
      </div>
    </div>
  );
}
