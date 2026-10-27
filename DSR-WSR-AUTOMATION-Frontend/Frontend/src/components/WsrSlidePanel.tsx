import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  ClipboardList,
  Loader2,
  RefreshCw,
  X,
  XCircle,
} from "lucide-react";
import {
  wsrPreviewImageUrl,
  type WsrAnnotationItem,
  type WsrFindingSeverity,
  type WsrValidationFinding,
  type WsrValidationSlideSummary,
} from "@/api/wsr";
import type { WsrValidationState } from "@/components/wsr/useWsrValidation";

/* ── Slide Review button (with finding-count badge) ─────────────────────── */

interface SlideReviewButtonProps {
  onClick: () => void;
  /** Total findings; `null` while validation has not produced a report yet. */
  findingCount?: number | null;
  className?: string;
}

export function SlideReviewButton({ onClick, findingCount, className = "" }: SlideReviewButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-brand-black border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors ${className}`}
    >
      <ClipboardCheck className="w-3.5 h-3.5" />
      Slide Review
      {findingCount != null && findingCount > 0 ? (
        <span
          className="min-w-[18px] h-[18px] px-1 rounded-full bg-brand-red text-white text-[10px] font-bold leading-[18px] text-center"
          aria-label={`${findingCount} findings`}
        >
          {findingCount}
        </span>
      ) : null}
      {findingCount === 0 ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-green-600" aria-label="No findings" />
      ) : null}
    </button>
  );
}

/* ── Re-check deck button (pull SharePoint copy + re-validate) ──────────── */

interface RecheckDeckButtonProps {
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
}

/** Separate from `SlideReviewButton`: Slide Review stays instant, this one re-analyses. */
export function RecheckDeckButton({
  onClick,
  loading = false,
  disabled = false,
  className = "",
}: RecheckDeckButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || disabled}
      title="Pull the latest copy from SharePoint (if it changed) and re-run the slide checks"
      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-brand-red bg-white border border-brand-red/30 rounded-lg hover:bg-brand-red/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
      {loading ? "Re-checking…" : "Re-check deck"}
    </button>
  );
}

/* ── Small presentational pieces ────────────────────────────────────────── */

function SeverityChip({ severity }: { severity: WsrFindingSeverity }) {
  const fail = severity === "fail";
  const Icon = fail ? XCircle : AlertTriangle;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold text-white ${
        fail ? "bg-brand-red" : "bg-amber-600"
      }`}
    >
      <Icon className="w-3 h-3" aria-hidden />
      {fail ? "Must fix" : "Polish"}
    </span>
  );
}

function pillClasses(count: number, selected: boolean): string {
  const tone = count === 0 ? "bg-green-500" : count <= 2 ? "bg-brand-orange" : "bg-brand-red";
  const ring = selected
    ? "ring-2 ring-white ring-offset-2 ring-offset-[#0a0a10] shadow-[0_0_10px_rgba(255,255,255,0.25)]"
    : "";
  return `shrink-0 min-w-[26px] h-6 px-1.5 rounded-md text-[11px] font-bold text-white transition-all hover:brightness-110 ${tone} ${ring}`;
}

function LegendItem({ dot, label }: { dot: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${dot}`} aria-hidden />
      {label}
    </span>
  );
}

function FindingCard({
  finding,
  active,
  selectable,
  onSelect,
}: {
  finding: WsrValidationFinding;
  active: boolean;
  selectable: boolean;
  onSelect: () => void;
}) {
  const steps = finding.fix_steps ?? [];
  return (
    <div
      role={selectable ? "button" : undefined}
      tabIndex={selectable ? 0 : undefined}
      onClick={selectable ? onSelect : undefined}
      onKeyDown={
        selectable
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect();
              }
            }
          : undefined
      }
      className={`rounded-xl border bg-[#1c1c23]/60 backdrop-blur-sm text-left transition-colors ${
        active && selectable ? "border-white/30" : "border-white/10"
      } ${selectable ? "cursor-pointer hover:border-white/25" : ""}`}
    >
      <div className="px-4 pt-3.5 pb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityChip severity={finding.severity} />
          <span className="text-[10px] font-mono tracking-wide text-gray-500">
            {finding.rule_id}
          </span>
        </div>
        <p className="text-[13px] font-bold text-white mt-2 leading-snug">{finding.issue}</p>
        {finding.where ? (
          <p className="text-xs mt-1 text-gray-400">
            <span className="text-gray-500">Where:</span> {finding.where}
          </p>
        ) : null}
      </div>

      {steps.length > 0 ? (
        <div className="border-t border-white/10 px-4 pt-3 pb-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            How to fix
          </p>
          <ol className="mt-2 space-y-1.5">
            {steps.map((step, index) => (
              <li key={index} className="flex items-start gap-2 text-xs text-gray-200 leading-snug">
                <span className="mt-px w-4 h-4 shrink-0 rounded-full bg-brand-red text-white text-[9px] font-bold flex items-center justify-center">
                  {index + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {finding.why ? (
        <p className="px-4 pb-3.5 pt-0.5 text-xs italic text-gray-500 leading-snug">
          {finding.why}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Floating drawer pinned to the bottom of the image area. It overlays the slide
 * image (it never pushes it), following the design reference.
 */
function FindingDrawer({
  findings,
  annotations,
  selectedAnnotationIdx,
  onSelectFinding,
  maxHeight,
  expanded,
  onToggle,
}: {
  findings: WsrValidationFinding[];
  annotations: WsrAnnotationItem[];
  selectedAnnotationIdx: number;
  onSelectFinding: (finding: WsrValidationFinding) => void;
  maxHeight: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const activeRule = annotations[selectedAnnotationIdx]?.rule_id.toLowerCase() ?? null;

  if (findings.length === 0) {
    return (
      <div className="absolute inset-x-0 bottom-0 z-10 h-8 bg-[#050508] flex items-center justify-center gap-1.5 text-xs font-medium text-gray-300 select-none">
        <ChevronUp className="w-3.5 h-3.5" aria-hidden />
        No findings for this slide
      </div>
    );
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={false}
        className="absolute inset-x-0 bottom-0 z-10 flex items-center justify-center gap-2 w-full h-8 bg-black/40 backdrop-blur-sm text-xs font-medium text-gray-200 hover:bg-black/55 hover:text-white transition-colors"
      >
        <ChevronUp className="w-3.5 h-3.5" aria-hidden />
        {findings.length} {findings.length === 1 ? "finding" : "findings"} — tap to review
        <ChevronUp className="w-3.5 h-3.5" aria-hidden />
      </button>
    );
  }

  return (
    <div className="absolute inset-x-0 bottom-0 z-10 flex flex-col bg-black/40 backdrop-blur-sm border-t border-white/5">
      <div
        className="overflow-y-auto px-3 pt-3 space-y-2 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
        style={{ maxHeight }}
      >
        {findings.map((finding, index) => (
          <FindingCard
            key={`${finding.rule_id}-${index}`}
            finding={finding}
            active={activeRule === finding.rule_id.toLowerCase()}
            selectable={findings.length > 1}
            onSelect={() => onSelectFinding(finding)}
          />
        ))}
      </div>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded
        className="w-full h-9 shrink-0 flex items-center justify-center gap-1.5 text-xs font-medium text-gray-200 hover:bg-black/20 hover:text-white transition-colors"
      >
        <ChevronDown className="w-3.5 h-3.5" aria-hidden />
        Close findings
      </button>
    </div>
  );
}

/* ── Panel ──────────────────────────────────────────────────────────────── */

interface WsrSlidePanelProps {
  startDate: string;
  endDate: string;
  variant?: number;
  /** Validation state from `useWsrValidation` (owned by the parent so the badge stays in sync). */
  validation: WsrValidationState;
  /** Normal content shown behind the review overlay. */
  defaultContent: ReactNode;
  /** Controlled open state. When omitted the panel manages its own state. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

function buildSummaries(validation: WsrValidationState): WsrValidationSlideSummary[] {
  const report = validation.report;
  if (!report) return [];
  if (report.slide_summaries && report.slide_summaries.length > 0) {
    return [...report.slide_summaries].sort((a, b) => a.slide_number - b.slide_number);
  }
  // Older (v1) reports have no per-slide summaries: derive them from the findings.
  const bySlide = new Map<number, WsrValidationSlideSummary>();
  for (const finding of report.findings) {
    const entry: WsrValidationSlideSummary = bySlide.get(finding.slide_number) ?? {
      slide_index: finding.slide_index,
      slide_number: finding.slide_number,
      slide_title: finding.slide_title ?? "",
      pass: true,
      fail_count: 0,
      warn_count: 0,
    };
    if (finding.severity === "fail") {
      entry.fail_count += 1;
      entry.pass = false;
    } else {
      entry.warn_count += 1;
    }
    bySlide.set(finding.slide_number, entry);
  }
  return [...bySlide.values()].sort((a, b) => a.slide_number - b.slide_number);
}

export function WsrSlidePanel({
  startDate,
  endDate,
  variant = 1,
  validation,
  defaultContent,
  open: openProp,
  onOpenChange,
}: WsrSlidePanelProps) {
  const [openInternal, setOpenInternal] = useState(false);
  const open = openProp ?? openInternal;
  const setOpen = (value: boolean) => {
    if (openProp === undefined) setOpenInternal(value);
    onOpenChange?.(value);
  };

  const { phase, report, annotations, message, rerun, refresh } = validation;
  const summaries = useMemo(() => buildSummaries(validation), [validation]);

  const [selectedSlide, setSelectedSlide] = useState<number | null>(null);
  const [selectedAnnotationIdx, setSelectedAnnotationIdx] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Default to the first slide that has findings (or the first slide).
  useEffect(() => {
    if (summaries.length === 0) {
      setSelectedSlide(null);
      return;
    }
    setSelectedSlide((current) => {
      if (current != null && summaries.some((s) => s.slide_number === current)) return current;
      const firstWithFindings = summaries.find((s) => s.fail_count + s.warn_count > 0);
      return (firstWithFindings ?? summaries[0]).slide_number;
    });
  }, [summaries]);

  // Each slide starts with the drawer collapsed ("tap to review").
  useEffect(() => {
    setSelectedAnnotationIdx(0);
    setDrawerOpen(false);
  }, [selectedSlide]);

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (openProp === undefined) setOpenInternal(false);
        onOpenChange?.(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, openProp, onOpenChange]);

  // Cap the expanded findings list at ~60% of the image area (it scrolls beyond that).
  const imageAreaRef = useRef<HTMLDivElement>(null);
  const [drawerMaxHeight, setDrawerMaxHeight] = useState(240);
  useEffect(() => {
    const element = imageAreaRef.current;
    if (!open || !element) return;
    const observer = new ResizeObserver(([entry]) => {
      setDrawerMaxHeight(Math.max(120, Math.floor(entry.contentRect.height * 0.62) - 36));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [open, phase]);

  const slideFindings = useMemo(
    () => (report?.findings ?? []).filter((f) => f.slide_number === selectedSlide),
    [report, selectedSlide],
  );
  const slideAnnotations = useMemo(
    () => annotations.filter((a) => a.slide_number === selectedSlide),
    [annotations, selectedSlide],
  );
  const activeAnnotation: WsrAnnotationItem | undefined = slideAnnotations[selectedAnnotationIdx];
  const selectedSummary = summaries.find((s) => s.slide_number === selectedSlide);

  const selectFinding = (finding: WsrValidationFinding) => {
    const index = slideAnnotations.findIndex(
      (a) => a.rule_id.toLowerCase() === finding.rule_id.toLowerCase(),
    );
    if (index >= 0) setSelectedAnnotationIdx(index);
  };

  const running = phase === "loading" || phase === "pending";

  const renderBody = () => {
    if (running) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6 text-gray-300">
          <Loader2 className="w-9 h-9 animate-spin text-brand-orange mb-3" />
          <p className="text-sm font-semibold">Checking the deck…</p>
          <p className="text-xs text-gray-500 mt-1 max-w-sm">
            Validation runs after generation and usually takes a minute. This panel updates
            automatically.
          </p>
        </div>
      );
    }
    if (phase === "not_started") {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6 text-gray-300 gap-3">
          <ClipboardCheck className="w-10 h-10 text-gray-500" />
          <p className="text-sm font-semibold">This deck has not been reviewed yet</p>
          <button
            type="button"
            onClick={() => void rerun()}
            className="px-4 py-2 text-xs font-semibold text-white bg-brand-orange rounded-lg hover:bg-brand-orange-hover"
          >
            Run validation
          </button>
        </div>
      );
    }
    if (phase === "error" || phase === "timeout" || phase === "idle" || !report) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6 text-gray-300 gap-3">
          <AlertTriangle className="w-10 h-10 text-amber-400" />
          <p className="text-sm font-semibold">
            {phase === "timeout" ? "Still validating…" : "Validation unavailable"}
          </p>
          <p className="text-xs text-gray-500 max-w-md whitespace-pre-wrap">
            {message || "The review could not be loaded."}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={refresh}
              className="px-3 py-1.5 text-xs font-semibold text-gray-200 border border-white/20 rounded-lg hover:bg-white/10"
            >
              Check again
            </button>
            <button
              type="button"
              onClick={() => void rerun()}
              className="px-3 py-1.5 text-xs font-semibold text-white bg-brand-orange rounded-lg hover:bg-brand-orange-hover"
            >
              Run validation
            </button>
          </div>
        </div>
      );
    }

    const cleanSlide = selectedSlide != null && slideFindings.length === 0;

    return (
      <>
        {/* Image area — the findings drawer floats over its bottom edge */}
        <div ref={imageAreaRef} className="relative flex-1 min-h-0">
          {selectedSlide == null ? (
            <p className="absolute inset-0 flex items-center justify-center text-sm text-gray-400">
              No slides were analysed.
            </p>
          ) : cleanSlide ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6 pb-8">
              <span className="w-14 h-14 rounded-full bg-green-500/15 border border-green-500/40 flex items-center justify-center">
                <Check className="w-7 h-7 text-green-400" strokeWidth={2.5} aria-hidden />
              </span>
              <p className="mt-3 text-sm font-bold text-green-400">
                Slide {selectedSlide} — No issues found
              </p>
              {selectedSummary?.slide_title ? (
                <p className="mt-1 text-xs text-gray-400">{selectedSummary.slide_title}</p>
              ) : null}
              <p className="mt-1.5 text-[11px] text-gray-500">This slide passed all format checks</p>
            </div>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center px-3 pt-2.5 pb-2">
              <img
                key={activeAnnotation?.image_url ?? `plain-${selectedSlide}`}
                src={
                  activeAnnotation?.image_url ??
                  wsrPreviewImageUrl(startDate, endDate, selectedSlide, variant)
                }
                alt={
                  activeAnnotation
                    ? `Slide ${selectedSlide} annotated: ${activeAnnotation.rule_id}`
                    : `Slide ${selectedSlide}`
                }
                className="max-w-full max-h-full object-contain rounded-sm shadow-xl bg-white"
              />
            </div>
          )}

          {/* Annotation selector — only when a slide has several annotated images */}
          {!cleanSlide && slideAnnotations.length > 1 ? (
            <div className="absolute top-3.5 right-5 z-20 flex gap-1.5 max-w-[70%] overflow-x-auto rounded-full bg-black/60 backdrop-blur-sm p-1">
              {slideAnnotations.map((annotation, index) => (
                <button
                  key={annotation.filename}
                  type="button"
                  onClick={() => setSelectedAnnotationIdx(index)}
                  className={`shrink-0 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border transition-colors ${
                    index === selectedAnnotationIdx
                      ? "bg-white text-brand-black border-white"
                      : "text-gray-200 border-white/20 hover:bg-white/10"
                  }`}
                >
                  {annotation.rule_id}
                </button>
              ))}
            </div>
          ) : null}

          {!cleanSlide && selectedSlide != null && slideAnnotations.length === 0 ? (
            <div className="absolute top-3.5 left-5 z-20 px-2.5 py-1 rounded-md bg-black/70 text-gray-200 text-[11px]">
              No annotated image is available for this slide.
            </div>
          ) : null}

          {selectedSlide != null ? (
            <FindingDrawer
              findings={slideFindings}
              annotations={slideAnnotations}
              selectedAnnotationIdx={selectedAnnotationIdx}
              onSelectFinding={selectFinding}
              maxHeight={drawerMaxHeight}
              expanded={drawerOpen}
              onToggle={() => setDrawerOpen((value) => !value)}
            />
          ) : null}
        </div>

        {/* Slide-number rail: legend + colour-coded pills */}
        {summaries.length > 0 ? (
          <div className="shrink-0 border-t border-white/10 px-4 py-2.5 flex items-center gap-3">
            <div className="shrink-0 flex items-center gap-2.5 text-[10px] text-gray-400">
              <LegendItem dot="bg-green-500" label="OK" />
              <LegendItem dot="bg-brand-orange" label="1–2" />
              <LegendItem dot="bg-brand-red" label="3+" />
            </div>
            <span className="shrink-0 w-px h-5 bg-white/15" aria-hidden />
            <div className="flex items-center gap-1.5 overflow-x-auto px-1 py-1.5 -my-1.5">
              {summaries.map((summary) => {
                const count = summary.fail_count + summary.warn_count;
                return (
                  <button
                    key={summary.slide_number}
                    type="button"
                    onClick={() => setSelectedSlide(summary.slide_number)}
                    title={`${summary.slide_title || `Slide ${summary.slide_number}`} — ${
                      count === 0 ? "no issues" : `${count} finding${count === 1 ? "" : "s"}`
                    }`}
                    className={pillClasses(count, summary.slide_number === selectedSlide)}
                  >
                    {summary.slide_number}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </>
    );
  };

  const headerCount = slideFindings.length;
  const showSlideHeader = phase === "ready" && report && selectedSummary;

  return (
    <div className="relative flex-1 min-h-0 min-w-0 flex flex-col">
      {defaultContent}
      {open ? (
        <div
          role="dialog"
          aria-label="Slide review"
          className="absolute inset-3 z-40 rounded-2xl flex flex-col overflow-hidden border border-white/10 shadow-2xl backdrop-blur-md"
          style={{ background: "rgba(10, 10, 15, 0.92)" }}
        >
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-white/10 shrink-0">
            <div className="flex items-center gap-2 min-w-0 text-xs">
              <span
                className="shrink-0"
                title={
                  report
                    ? `${report.summary.fail} must fix · ${report.summary.warn} polish${
                        report.deck_pass ? " · deck passes" : ""
                      }`
                    : "Slide review"
                }
              >
                <ClipboardList className="w-4 h-4 text-brand-red" aria-hidden />
              </span>
              {showSlideHeader ? (
                <>
                  <span className="shrink-0 px-2 py-0.5 rounded-md bg-white/10 text-white text-[11px] font-bold">
                    Slide {selectedSummary.slide_number}
                  </span>
                  {selectedSummary.slide_title ? (
                    <span className="truncate text-gray-300">{selectedSummary.slide_title}</span>
                  ) : null}
                  {headerCount > 0 ? (
                    <span className="shrink-0 font-medium text-red-500">
                      · {headerCount} {headerCount === 1 ? "finding" : "findings"}
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="font-semibold text-white">Slide Review</span>
              )}
            </div>
            <div className="flex items-center gap-0.5 shrink-0">
              {phase === "ready" ? (
                <button
                  type="button"
                  onClick={() => void rerun()}
                  title="Run validation again"
                  className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/10"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close slide review"
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="flex-1 min-h-0 flex flex-col">{renderBody()}</div>
        </div>
      ) : null}
    </div>
  );
}
