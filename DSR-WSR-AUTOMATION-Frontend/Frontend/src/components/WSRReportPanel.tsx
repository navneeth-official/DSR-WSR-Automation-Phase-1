import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Download, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import {
  checkWsrGeneration,
  fetchWsrPreviewSlides,
  fetchWsrWeek,
  startWsrJob,
  waitForWsrJob,
  wsrDownloadUrl,
  type WsrGenerateResponse,
  type WsrPreviewSlide,
} from "@/api/wsr";
import { WSRPptEditor } from "@/components/ppt-editor/WSRPptEditor";
import { WSRPptViewer } from "@/components/WSRPptViewer";
import { FloatingNotice, useFloatingNotice } from "@/components/ui/FloatingNotice";
import { VariantRibbon, variantBadgeLabel } from "@/components/wsr/VariantRibbon";

interface WSRReportPanelProps {
  startDate: string;
  endDate: string;
  /** Saved template id used as the reference deck for WSR engine v2 generation. */
  templateId?: string | null;
  /** Deck variant when viewing an existing report (1=primary, 2=V2, …). */
  variant?: number;
  /** `viewer` = thumbnails + slide preview only; `editor` = full in-browser PPT editor */
  mode?: "viewer" | "editor";
  /** When false, only load an existing deck (no background generation). */
  autoGenerate?: boolean;
  /** When true, always queue a fresh generation instead of reusing an on-disk deck. */
  alwaysRegenerate?: boolean;
  /** When set, shows a Change template control in the action bar. */
  onChangeTemplate?: () => void;
  showRegenerate?: boolean;
  onBack?: () => void;
}

export function WSRReportPanel({
  startDate,
  endDate,
  templateId,
  variant = 1,
  mode = "editor",
  autoGenerate = true,
  alwaysRegenerate = false,
  showRegenerate = true,
  onChangeTemplate,
  onBack,
}: WSRReportPanelProps) {
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Loading WSR deck…");
  const [error, setError] = useState("");
  const [duplicateAlert, setDuplicateAlert] = useState("");
  const {
    message: variantNotice,
    exiting: variantNoticeExiting,
    show: showVariantNotice,
    dismiss: dismissVariantNotice,
  } = useFloatingNotice();
  const [previewError, setPreviewError] = useState("");
  const [result, setResult] = useState<WsrGenerateResponse | null>(null);
  const [previewSlides, setPreviewSlides] = useState<WsrPreviewSlide[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [deckReloadKey, setDeckReloadKey] = useState(0);
  const [activeVariant, setActiveVariant] = useState(variant);

  const runGenerate = useCallback(
    async (force = true) => {
      if (!templateId) {
        setError("Select a WSR template before generating.");
        return;
      }
      setLoading(true);
      setLoadingMessage("Checking existing WSR reports…");
      setError("");
      setDuplicateAlert("");
      dismissVariantNotice();
      try {
        const check = await checkWsrGeneration(startDate, endDate, templateId);
        if (!check.can_generate) {
          setDuplicateAlert(
            `${check.message} Open Weekly Reports → View WSR to review the existing deck.`,
          );
          return;
        }
        if (check.reason === "different_template") {
          showVariantNotice(check.message);
        }
        setLoadingMessage("Generating WSR deck in the background…");
        await startWsrJob({
          start_date: startDate,
          end_date: endDate,
          template_id: templateId,
          force,
        });
        const response = await waitForWsrJob(startDate, endDate);
        const resolvedVariant = response.variant ?? check.variant ?? 1;
        setActiveVariant(resolvedVariant);
        if (check.reason === "different_template" || resolvedVariant > 1) {
          showVariantNotice(
            check.message ||
              `This deck was saved as ${response.variant_label ?? `${variantBadgeLabel(resolvedVariant)} WSR`}.`,
          );
        }
        setResult(response);
        setDeckReloadKey((k) => k + 1);
      } catch (err) {
        setResult(null);
        setError(err instanceof Error ? err.message : "WSR generation failed");
      } finally {
        setLoading(false);
      }
    },
    [startDate, endDate, templateId, dismissVariantNotice, showVariantNotice],
  );

  useEffect(() => {
    const controller = new AbortController();

    setResult(null);
    setError("");
    setDuplicateAlert("");
    dismissVariantNotice();
    setPreviewError("");
    setLoading(true);
    setLoadingMessage("Loading WSR deck…");
    setActiveVariant(variant);

    void (async () => {
      try {
        if (!alwaysRegenerate) {
          const existing = await fetchWsrWeek(startDate, endDate, variant);
          if (controller.signal.aborted) return;

          if (existing) {
            setActiveVariant(existing.variant ?? variant);
            setResult(existing);
            setLoading(false);
            return;
          }
        }

        if (!autoGenerate) {
          setError("No WSR deck found for this week.");
          setLoading(false);
          return;
        }

        if (!templateId) {
          setError("Select a WSR template before generating.");
          setLoading(false);
          return;
        }

        const check = await checkWsrGeneration(startDate, endDate, templateId);
        if (controller.signal.aborted) return;

        if (!check.can_generate) {
          setDuplicateAlert(
            `${check.message} Open Weekly Reports → View WSR to review the existing deck.`,
          );
          setLoading(false);
          return;
        }

        if (check.reason === "different_template") {
          showVariantNotice(check.message);
        }

        setLoadingMessage("Generating WSR deck in the background…");
        await startWsrJob({
          start_date: startDate,
          end_date: endDate,
          template_id: templateId,
          force: alwaysRegenerate,
        });
        const response = await waitForWsrJob(startDate, endDate, {
          signal: controller.signal,
        });
        if (!controller.signal.aborted) {
          const resolvedVariant = response.variant ?? check.variant ?? 1;
          setActiveVariant(resolvedVariant);
          if (check.reason === "different_template" || resolvedVariant > 1) {
            showVariantNotice(
              check.message ||
                `This deck was saved as ${response.variant_label ?? `${variantBadgeLabel(resolvedVariant)} WSR`}.`,
            );
          }
          setResult(response);
          setDeckReloadKey((k) => k + 1);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setResult(null);
          setError(err instanceof Error ? err.message : "WSR generation failed");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [startDate, endDate, autoGenerate, alwaysRegenerate, templateId, variant, dismissVariantNotice, showVariantNotice]);

  useEffect(() => {
    if (mode !== "viewer" || !result) {
      setPreviewSlides([]);
      setPreviewError("");
      setPreviewLoading(false);
      return;
    }

    if (result.preview_slides.length > 0) {
      setPreviewSlides(result.preview_slides);
      setPreviewError("");
      setPreviewLoading(false);
      return;
    }

    let cancelled = false;
    setPreviewSlides([]);
    setPreviewError("");
    setPreviewLoading(true);
    void (async () => {
      try {
        const slides = await fetchWsrPreviewSlides(startDate, endDate, activeVariant);
        if (!cancelled) {
          setPreviewSlides(slides);
          if (slides.length === 0) {
            setPreviewError(
              "Slide previews could not be generated for this deck. Try Regenerate, or download the PPT.",
            );
          }
        }
      } catch (err) {
        if (!cancelled) {
          setPreviewSlides([]);
          setPreviewError(
            err instanceof Error
              ? err.message
              : "Slide previews are unavailable for this deck.",
          );
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [mode, result, startDate, endDate, activeVariant]);

  const downloadUrl =
    result?.download_url ?? wsrDownloadUrl(startDate, endDate, activeVariant);
  const cloudUrl = result?.cloud_web_url ?? result?.onedrive_web_url ?? null;
  const cloudOpenLabel =
    result?.cloud_provider === "google_drive"
      ? "Open in Google Drive"
      : result?.cloud_provider === "onedrive"
        ? "Open in OneDrive"
        : "Open in cloud";

  return (
    <div className="relative flex flex-col h-full min-h-0 bg-brand-cream">
      <div className="relative z-10 flex items-center justify-between gap-3 px-6 py-3 bg-white border-b border-gray-200 flex-shrink-0 overflow-hidden">
        {activeVariant > 1 ? (
          <VariantRibbon label={variantBadgeLabel(activeVariant)} />
        ) : null}
        <div className="flex items-center gap-3 min-w-0">
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 flex-shrink-0"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back
            </button>
          ) : null}
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-800">WSR PowerPoint</h3>
            <p className="text-xs text-gray-400 mt-0.5 truncate">
            {startDate} → {endDate}
            {result
              ? ` · ${result.meta.story_count} stories · ${result.meta.slide_count} track slides`
              : ""}
            {result && !loading
              ? ` · ${result.meta.titles_from_db ?? result.meta.titles_reused} DB titles${
                  (result.meta.titles_fallback_summary ?? 0) > 0
                    ? `, ${result.meta.titles_fallback_summary} summary fallback`
                    : ""
                }`
              : ""}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {onChangeTemplate ? (
            <button
              type="button"
              onClick={onChangeTemplate}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-brand-red border border-brand-red/30 rounded-lg hover:bg-brand-red/10 disabled:opacity-50"
            >
              Change template
            </button>
          ) : null}
          {showRegenerate ? (
            <button
              type="button"
              onClick={() => void runGenerate(true)}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              Regenerate
            </button>
          ) : null}
          <a
            href={downloadUrl}
            download={result?.filename ?? `WSR_${startDate}_${endDate}.pptx`}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white rounded-lg transition-colors ${
              loading || error
                ? "pointer-events-none opacity-50 bg-brand-orange/40"
                : "bg-brand-orange hover:bg-brand-orange-hover"
            }`}
          >
            <Download className="w-3.5 h-3.5" />
            Download PPT
          </a>
          {cloudUrl ? (
            <a
              href={cloudUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-brand-red/30 text-brand-red rounded-lg hover:bg-brand-red/10"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {cloudOpenLabel}
            </a>
          ) : null}
        </div>
      </div>

      {variantNotice ? (
        <FloatingNotice
          message={variantNotice}
          exiting={variantNoticeExiting}
          onDismiss={dismissVariantNotice}
          tone="info"
          className="absolute top-4 left-1/2 z-20 w-[min(calc(100%-3rem),32rem)] -translate-x-1/2 text-xs"
        />
      ) : null}

      <div className="flex-1 min-h-0 overflow-hidden">
        {loading && (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <Loader2 className="w-10 h-10 text-brand-red animate-spin mb-4" />
            <p className="text-sm font-semibold text-gray-700">{loadingMessage}</p>
            <p className="text-xs text-gray-400 mt-1 max-w-md">
              {startDate} → {endDate}. Building slides from database titles; this may take a
              minute for large weeks.
            </p>
          </div>
        )}

        {!loading && duplicateAlert && (
          <div className="max-w-2xl mx-auto bg-amber-50 border border-amber-200 rounded-xl p-5 m-6">
            <p className="text-sm font-semibold text-amber-800">WSR already generated</p>
            <p className="text-xs text-amber-700 mt-2 whitespace-pre-wrap">{duplicateAlert}</p>
          </div>
        )}

        {!loading && error && (
          <div className="max-w-2xl mx-auto bg-red-50 border border-red-200 rounded-xl p-5 m-6">
            <p className="text-sm font-semibold text-red-700">
              {autoGenerate ? "Generation failed" : "Unable to load WSR"}
            </p>
            <p className="text-xs text-red-600 mt-2 whitespace-pre-wrap">{error}</p>
            {autoGenerate ? (
              <button
                type="button"
                onClick={() => void runGenerate(true)}
                className="mt-4 text-xs font-semibold text-red-700 underline"
              >
                Try again
              </button>
            ) : onBack ? (
              <button
                type="button"
                onClick={onBack}
                className="mt-4 text-xs font-semibold text-red-700 underline"
              >
                Back to all reports
              </button>
            ) : null}
          </div>
        )}

        {!loading && !error && result && (
          <div className="h-full min-h-0">
            {mode === "viewer" ? (
              previewLoading && previewSlides.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center px-6">
                  <Loader2 className="w-8 h-8 text-brand-red animate-spin mb-3" />
                  <p className="text-sm font-medium text-gray-700">Loading slide previews…</p>
                  <p className="text-xs text-gray-400 mt-1 max-w-md">
                    Rendering thumbnails from the generated deck.
                  </p>
                </div>
              ) : previewSlides.length > 0 ? (
                <WSRPptViewer
                  previewSlides={previewSlides}
                  filename={result.filename}
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center px-6">
                  <p className="text-sm font-medium text-gray-700">
                    Slide previews are not available
                  </p>
                  <p className="text-xs text-gray-500 mt-2 max-w-md">
                    {previewError ||
                      "Download the PPT to view the generated deck, or click Regenerate to rebuild previews."}
                  </p>
                  {showRegenerate && (
                    <button
                      type="button"
                      onClick={() => void runGenerate(true)}
                      className="mt-4 text-xs font-semibold text-brand-red underline"
                    >
                      Regenerate WSR
                    </button>
                  )}
                </div>
              )
            ) : (
              <WSRPptEditor
                key={`${startDate}-${endDate}-${deckReloadKey}`}
                startDate={startDate}
                endDate={endDate}
                filename={result.filename}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
