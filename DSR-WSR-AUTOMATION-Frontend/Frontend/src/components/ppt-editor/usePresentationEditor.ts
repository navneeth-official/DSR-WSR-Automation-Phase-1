import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EditorSlide, PresentationDocument, SlideElement, TextElement } from "./types";
import { CANVAS_HEIGHT, CANVAS_WIDTH, DEFAULT_TEXT_STYLE } from "./types";
import { cloneDocument, createId } from "./utils";

const MAX_HISTORY = 40;

export interface UsePresentationEditorResult {
  document: PresentationDocument | null;
  activeSlide: EditorSlide | null;
  activeSlideIndex: number;
  selectedIds: string[];
  selectedElements: SlideElement[];
  zoom: number;
  canUndo: boolean;
  canRedo: boolean;
  fitToView?: () => void;
  setDocument: (doc: PresentationDocument) => void;
  replaceDocument: (doc: PresentationDocument) => void;
  setActiveSlideIndex: (index: number) => void;
  setZoom: (zoom: number) => void;
  selectElements: (ids: string[]) => void;
  clearSelection: () => void;
  updateElement: (id: string, patch: Partial<SlideElement>, options?: { history?: boolean }) => void;
  addTextBox: () => void;
  addShape: () => void;
  addImageFromFile: (file: File) => Promise<void>;
  duplicateSelected: () => void;
  deleteSelected: () => void;
  addSlide: () => void;
  duplicateSlide: () => void;
  deleteSlide: () => void;
  moveSlide: (from: number, to: number) => void;
  undo: () => void;
  redo: () => void;
  copySelected: () => void;
  pasteClipboard: () => void;
}

export function usePresentationEditor(): UsePresentationEditorResult {
  const [document, setDocumentState] = useState<PresentationDocument | null>(null);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [zoom, setZoom] = useState(1);
  const [history, setHistory] = useState<PresentationDocument[]>([]);
  const [future, setFuture] = useState<PresentationDocument[]>([]);
  const clipboardRef = useRef<SlideElement[]>([]);

  const commit = useCallback((next: PresentationDocument) => {
    setDocumentState((prev) => {
      if (prev) {
        setHistory((h) => [...h.slice(-MAX_HISTORY + 1), cloneDocument(prev)]);
      }
      setFuture([]);
      return next;
    });
  }, []);

  const setDocument = useCallback((doc: PresentationDocument) => {
    setHistory([]);
    setFuture([]);
    setDocumentState(doc);
    setActiveSlideIndex(0);
    setSelectedIds([]);
  }, []);

  const replaceDocument = useCallback((doc: PresentationDocument) => {
    setDocumentState(doc);
  }, []);

  const activeSlide = useMemo(
    () => document?.slides[activeSlideIndex] ?? null,
    [document, activeSlideIndex],
  );

  const selectedElements = useMemo(() => {
    if (!activeSlide) return [];
    return activeSlide.elements.filter((el) => selectedIds.includes(el.id));
  }, [activeSlide, selectedIds]);

  const applySlidePatch = useCallback(
    (mutator: (slide: EditorSlide) => EditorSlide, recordHistory: boolean) => {
      if (!document) return;
      const slides = document.slides.map((slide, idx) =>
        idx === activeSlideIndex ? mutator(slide) : slide,
      );
      const next = { ...document, slides };
      if (recordHistory) {
        commit(next);
      } else {
        setDocumentState(next);
      }
    },
    [document, activeSlideIndex, commit],
  );

  const updateElement = useCallback(
    (id: string, patch: Partial<SlideElement>, options?: { history?: boolean }) => {
      const recordHistory = options?.history !== false;
      applySlidePatch(
        (slide) => ({
          ...slide,
          elements: slide.elements.map((el) =>
            el.id === id ? ({ ...el, ...patch } as SlideElement) : el,
          ),
        }),
        recordHistory,
      );
    },
    [applySlidePatch],
  );

  const mutateSlide = useCallback(
    (mutator: (slide: EditorSlide) => EditorSlide) => {
      applySlidePatch(mutator, true);
    },
    [applySlidePatch],
  );

  const addTextBox = useCallback(() => {
    const el: TextElement = {
      id: createId(),
      type: "text",
      x: 120,
      y: 120,
      width: 320,
      height: 80,
      rotation: 0,
      text: "Double-click to edit text",
      style: { ...DEFAULT_TEXT_STYLE },
    };
    mutateSlide((slide) => ({
      ...slide,
      elements: [...slide.elements, el],
    }));
    setSelectedIds([el.id]);
  }, [mutateSlide]);

  const addShape = useCallback(() => {
    mutateSlide((slide) => ({
      ...slide,
      elements: [
        ...slide.elements,
        {
          id: createId(),
          type: "shape",
          shapeKind: "rect",
          x: 200,
          y: 200,
          width: 200,
          height: 120,
          rotation: 0,
          fill: "#e0e7ff",
          stroke: "#6366f1",
          strokeWidth: 2,
        },
      ],
    }));
  }, [mutateSlide]);

  const addImageFromFile = useCallback(
    async (file: File) => {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error("Failed to read image"));
        reader.readAsDataURL(file);
      });
      const img = new Image();
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error("Invalid image"));
        img.src = dataUrl;
      });
      const maxW = 400;
      const scale = img.width > maxW ? maxW / img.width : 1;
      const width = img.width * scale;
      const height = img.height * scale;
      const id = createId();
      mutateSlide((slide) => ({
        ...slide,
        elements: [
          ...slide.elements,
          {
            id,
            type: "image",
            x: 100,
            y: 100,
            width,
            height,
            rotation: 0,
            src: dataUrl,
          },
        ],
      }));
      setSelectedIds([id]);
    },
    [mutateSlide],
  );

  const duplicateSelected = useCallback(() => {
    if (!selectedElements.length) return;
    const clones = selectedElements.map((el) => ({
      ...el,
      id: createId(),
      x: el.x + 20,
      y: el.y + 20,
    }));
    mutateSlide((slide) => ({
      ...slide,
      elements: [...slide.elements, ...clones],
    }));
    setSelectedIds(clones.map((c) => c.id));
  }, [mutateSlide, selectedElements]);

  const deleteSelected = useCallback(() => {
    if (!selectedIds.length) return;
    mutateSlide((slide) => ({
      ...slide,
      elements: slide.elements.filter((el) => !selectedIds.includes(el.id)),
    }));
    setSelectedIds([]);
  }, [mutateSlide, selectedIds]);

  const addSlide = useCallback(() => {
    if (!document) return;
    const index = document.slides.length + 1;
    const slide: EditorSlide = {
      id: createId(),
      index,
      title: `Slide ${index}`,
      background: "#ffffff",
      backgroundImage: null,
      elements: [],
    };
    commit({ ...document, slides: [...document.slides, slide] });
    setActiveSlideIndex(document.slides.length);
    setSelectedIds([]);
  }, [commit, document]);

  const duplicateSlide = useCallback(() => {
    if (!document || !activeSlide) return;
    const copy: EditorSlide = {
      ...cloneDocument({ id: "", filename: "", canvasWidth: 0, canvasHeight: 0, slides: [activeSlide] }).slides[0],
      id: createId(),
      index: document.slides.length + 1,
      title: `${activeSlide.title} (copy)`,
      elements: activeSlide.elements.map((el) => ({ ...el, id: createId() })),
    };
    const slides = [...document.slides];
    slides.splice(activeSlideIndex + 1, 0, copy);
    const reindexed = slides.map((s, i) => ({ ...s, index: i + 1 }));
    commit({ ...document, slides: reindexed });
    setActiveSlideIndex(activeSlideIndex + 1);
  }, [activeSlide, activeSlideIndex, commit, document]);

  const deleteSlide = useCallback(() => {
    if (!document || document.slides.length <= 1) return;
    const slides = document.slides
      .filter((_, i) => i !== activeSlideIndex)
      .map((s, i) => ({ ...s, index: i + 1 }));
    commit({ ...document, slides });
    setActiveSlideIndex(Math.max(0, activeSlideIndex - 1));
    setSelectedIds([]);
  }, [activeSlideIndex, commit, document]);

  const moveSlide = useCallback(
    (from: number, to: number) => {
      if (!document || from === to) return;
      const slides = [...document.slides];
      const [item] = slides.splice(from, 1);
      slides.splice(to, 0, item);
      commit({
        ...document,
        slides: slides.map((s, i) => ({ ...s, index: i + 1 })),
      });
      setActiveSlideIndex(to);
    },
    [commit, document],
  );

  const undo = useCallback(() => {
    setHistory((h) => {
      if (!h.length || !document) return h;
      const prev = h[h.length - 1];
      setFuture((f) => [cloneDocument(document), ...f]);
      setDocumentState(prev);
      return h.slice(0, -1);
    });
  }, [document]);

  const redo = useCallback(() => {
    setFuture((f) => {
      if (!f.length || !document) return f;
      const next = f[0];
      setHistory((h) => [...h, cloneDocument(document)]);
      setDocumentState(next);
      return f.slice(1);
    });
  }, [document]);

  const copySelected = useCallback(() => {
    clipboardRef.current = selectedElements.map((el) => ({ ...el }));
  }, [selectedElements]);

  const pasteClipboard = useCallback(() => {
    if (!clipboardRef.current.length) return;
    const clones = clipboardRef.current.map((el) => ({
      ...el,
      id: createId(),
      x: el.x + 24,
      y: el.y + 24,
    }));
    mutateSlide((slide) => ({
      ...slide,
      elements: [...slide.elements, ...clones],
    }));
    setSelectedIds(clones.map((c) => c.id));
  }, [mutateSlide]);

  useEffect(() => {
    setSelectedIds([]);
  }, [activeSlideIndex]);

  return {
    document,
    activeSlide,
    activeSlideIndex,
    selectedIds,
    selectedElements,
    zoom,
    canUndo: history.length > 0,
    canRedo: future.length > 0,
    setDocument,
    replaceDocument,
    setActiveSlideIndex,
    setZoom,
    selectElements: setSelectedIds,
    clearSelection: () => setSelectedIds([]),
    updateElement,
    addTextBox,
    addShape,
    addImageFromFile,
    duplicateSelected,
    deleteSelected,
    addSlide,
    duplicateSlide,
    deleteSlide,
    moveSlide,
    undo,
    redo,
    copySelected,
    pasteClipboard,
  };
}

export { CANVAS_WIDTH, CANVAS_HEIGHT };
