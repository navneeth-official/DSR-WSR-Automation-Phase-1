import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, Check, Loader2, Presentation, Upload, X } from "lucide-react";
import {
  cancelStagedWsrTemplate,
  fetchWsrTemplatePreviewSlides,
  fetchWsrTemplates,
  saveStagedWsrTemplate,
  stageWsrTemplate,
  type WsrPreviewSlide,
  type WsrTemplateItem,
} from "@/api/wsr";
import { WSRPptViewer } from "@/components/WSRPptViewer";

export const WSR_DRAFT_TEMPLATE_ID = "__draft__";

function formatUpdatedAt(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export interface WSRTemplateSelectorProps {
  selectedId: string | null;
  onSelectedIdChange: (id: string | null, item?: WsrTemplateItem | null) => void;
  onProceed?: (id: string, item: WsrTemplateItem) => void;
}

export function WSRTemplateSelector({
  selectedId,
  onSelectedIdChange,
  onProceed,
}: WSRTemplateSelectorProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [templates, setTemplates] = useState<WsrTemplateItem[]>([]);
  const [draft, setDraft] = useState<WsrTemplateItem | null>(null);
  const [previewSlides, setPreviewSlides] = useState<WsrPreviewSlide[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const selectedIdRef = useRef<string | null>(selectedId);
  const previewCacheRef = useRef<Map<string, WsrPreviewSlide[]>>(new Map());
  const onSelectRef = useRef(onSelectedIdChange);

  selectedIdRef.current = selectedId;
  onSelectRef.current = onSelectedIdChange;

  const allItems = draft ? [draft, ...templates] : templates;
  const selectedItem = allItems.find((item) => item.id === selectedId) ?? null;
  const isDraftSelected = selectedItem?.id === WSR_DRAFT_TEMPLATE_ID;
  const hasPendingDraft = draft != null;
  const canProceed =
    selectedItem != null &&
    !selectedItem.is_draft &&
    selectedItem.id !== WSR_DRAFT_TEMPLATE_ID;
  const continueBlocked = uploading || saving || previewLoading;

  const loadTemplates = useCallback(async (options?: { pickDefault?: boolean }) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetchWsrTemplates();
      setTemplates(response.templates);
      setDraft(response.draft);

      const items = response.draft
        ? [response.draft, ...response.templates]
        : response.templates;
      const currentId = selectedIdRef.current;

      if (options?.pickDefault) {
        const defaultItem = response.templates[0] ?? response.draft ?? null;
        onSelectRef.current(defaultItem?.id ?? null, defaultItem);
      } else if (currentId && !items.some((item) => item.id === currentId)) {
        const fallback = response.templates[0] ?? response.draft ?? null;
        onSelectRef.current(fallback?.id ?? null, fallback);
      }
    } catch (err) {
      setTemplates([]);
      setDraft(null);
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTemplates({ pickDefault: true });
  }, [loadTemplates]);

  useEffect(() => {
    if (!selectedItem) {
      setPreviewSlides([]);
      return;
    }

    const cached = previewCacheRef.current.get(selectedItem.id);
    if (cached?.length) {
      setPreviewSlides(cached);
      setPreviewLoading(false);
      return;
    }

    setPreviewSlides([]);
    let cancelled = false;
    setPreviewLoading(true);
    void (async () => {
      try {
        const slides = await fetchWsrTemplatePreviewSlides(selectedItem.id);
        if (cancelled) return;
        previewCacheRef.current.set(selectedItem.id, slides);
        setPreviewSlides(slides);
      } catch (err) {
        if (!cancelled) {
          const fallback = previewCacheRef.current.get(selectedItem.id) ?? [];
          setPreviewSlides(fallback);
          if (fallback.length === 0) {
            setError(err instanceof Error ? err.message : "Failed to load preview");
          }
        }
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedItem?.id]);

  const handleFileSelected = async (file: File | undefined) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pptx")) {
      setError("Please upload a .pptx file.");
      return;
    }

    setUploading(true);
    setError("");
    try {
      const staged = await stageWsrTemplate(file);
      setDraft(staged);
      previewCacheRef.current.set(staged.id, staged.preview_slides);
      setPreviewSlides(staged.preview_slides);
      onSelectedIdChange(staged.id, staged);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSaveDraft = async () => {
    setSaving(true);
    setError("");
    try {
      const saved = await saveStagedWsrTemplate();
      setDraft(null);
      previewCacheRef.current.delete(WSR_DRAFT_TEMPLATE_ID);
      await loadTemplates();
      previewCacheRef.current.delete(saved.id);
      onSelectedIdChange(saved.id, saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save template");
    } finally {
      setSaving(false);
    }
  };

  const handleCancelDraft = async () => {
    setSaving(true);
    setError("");
    try {
      await cancelStagedWsrTemplate();
      setDraft(null);
      const fallback = templates[0] ?? null;
      onSelectedIdChange(fallback?.id ?? null, fallback);
      await loadTemplates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to discard draft");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-1 min-h-0 bg-gray-50">
      <aside className="w-[220px] flex-shrink-0 border-r border-gray-200 bg-white flex flex-col min-h-0">
        <div className="px-3 py-2.5 border-b border-gray-200">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">
            WSR template
          </p>
          <p className="text-[10px] text-gray-400 mt-0.5">
            Newest first — select one for generation
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-2">
          {loading && (
            <div className="flex items-center justify-center py-8 text-gray-400">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          )}

          {!loading && allItems.length === 0 && (
            <div className="px-2 py-6 text-center">
              <Presentation className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-xs text-gray-500">No saved templates yet</p>
            </div>
          )}

          {!loading &&
            allItems.map((item) => {
              const selected = item.id === selectedItem?.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectedIdChange(item.id, item)}
                  className={`w-full rounded-lg border text-left overflow-hidden transition-all ${
                    selected
                      ? "border-brand-red ring-2 ring-brand-red/30 shadow-sm"
                      : "border-gray-200 hover:border-gray-300 hover:shadow-sm"
                  }`}
                >
                  <div className="aspect-[16/10] bg-gray-100 relative">
                    <img
                      src={item.thumbnail_url}
                      alt=""
                      className="w-full h-full object-cover"
                    />
                    {selected && (
                      <span className="absolute top-1.5 right-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-brand-red text-white">
                        <Check className="w-3 h-3" />
                      </span>
                    )}
                    {item.is_draft && (
                      <span className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-amber-500 text-[9px] font-semibold text-white uppercase">
                        New
                      </span>
                    )}
                  </div>
                  <div className="px-2 py-1.5 bg-white">
                    <p
                      className="text-[11px] font-medium text-gray-800 truncate"
                      title={item.original_filename}
                    >
                      {item.original_filename}
                    </p>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      {formatUpdatedAt(item.updated_at)}
                    </p>
                  </div>
                </button>
              );
            })}
        </div>

        <div className="p-2 border-t border-gray-200">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
            className="hidden"
            onChange={(e) => void handleFileSelected(e.target.files?.[0])}
          />
          <button
            type="button"
            disabled={uploading || saving || hasPendingDraft}
            onClick={() => fileInputRef.current?.click()}
            className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-brand-red/30 text-brand-red text-xs font-medium hover:bg-brand-red/10 disabled:opacity-60 disabled:cursor-not-allowed"
            title={
              hasPendingDraft
                ? "Save or cancel the uploaded template before uploading another."
                : undefined
            }
          >
            {uploading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Upload className="w-3.5 h-3.5" />
            )}
            {uploading ? "Uploading…" : "Upload template"}
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col min-h-0 bg-white">
        {isDraftSelected && (
          <div className="px-4 py-2.5 border-b border-gray-200 flex flex-wrap items-center justify-end gap-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={saving}
                onClick={() => void handleCancelDraft()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
              >
                <X className="w-3.5 h-3.5" />
                Cancel
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void handleSaveDraft()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-orange text-xs font-medium text-white hover:bg-brand-orange-hover disabled:opacity-60"
              >
                {saving ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Check className="w-3.5 h-3.5" />
                )}
                Save template
              </button>
            </div>
          </div>
        )}

        {error && (
          <p className="px-4 py-2 text-xs text-red-600 border-b border-red-100 bg-red-50">
            {error}
          </p>
        )}

        <div className="flex-1 min-h-[320px]">
          {previewLoading && previewSlides.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Loader2 className="w-6 h-6 animate-spin mb-2" />
              <p className="text-sm">Loading template preview…</p>
            </div>
          ) : previewSlides.length > 0 && selectedItem ? (
            <WSRPptViewer
              previewSlides={previewSlides}
              filename={selectedItem.original_filename}
              showSlideThumbnails={false}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <Presentation className="w-10 h-10 text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-600">No template selected</p>
              <p className="text-xs text-gray-400 mt-1 max-w-sm">
                Choose a saved template on the left or upload a new `.pptx` file to preview it
                here.
              </p>
            </div>
          )}
        </div>

        <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 flex flex-wrap items-center justify-between gap-3">
          <p className="text-[11px] text-gray-500">
            {uploading
              ? "Uploading template… Continue will be available when the upload finishes."
              : isDraftSelected
              ? "Save the uploaded template before continuing to WSR generation."
              : canProceed
                ? "Continue when you are ready to generate the WSR deck for the selected week."
                : "Select a saved template or upload and save a new one to continue."}
          </p>
          <button
            type="button"
            disabled={!canProceed || continueBlocked}
            onClick={() => {
              if (selectedItem && canProceed && !continueBlocked) {
                onProceed?.(selectedItem.id, selectedItem);
              }
            }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-orange text-white text-sm font-medium hover:bg-brand-orange-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Continue to generate WSR
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
