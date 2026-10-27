import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Download,
  ExternalLink,
  FileText,
  FolderOpen,
  Loader2,
  Presentation,
} from "lucide-react";
import { fetchWsrWeeks, wsrTemplateThumbnailUrl, type WsrWeekSummary } from "@/api/wsr";
import { FloatingNotice } from "@/components/ui/FloatingNotice";
import { RecheckDeckButton, SlideReviewButton, WsrSlidePanel } from "@/components/WsrSlidePanel";
import { VariantRibbon, variantBadgeLabel } from "@/components/wsr/VariantRibbon";
import { useRecheckDeck } from "@/components/wsr/useRecheckDeck";
import { useWsrValidation } from "@/components/wsr/useWsrValidation";

// list (weeks) → versions (week folder) → deck (details + slide review)
type ViewMode = "list" | "versions" | "deck";

const VIEW_PANEL_COUNT = 3;
const VIEW_TRANSITION_MS = 300;

interface WeekGroup {
  key: string;
  report_start_date: string;
  report_end_date: string;
  variants: WsrWeekSummary[];
}

function formatWeekRange(start: string, end: string): string {
  const mon = new Date(`${start}T00:00:00`);
  const fri = new Date(`${end}T00:00:00`);
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  return `${fmt(mon)} – ${fmt(fri)}`;
}

function formatGeneratedAt(iso: string): string {
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

function weekGroupKey(start: string, end: string): string {
  return `${start}_${end}`;
}

function DeckThumbnail({
  thumbnailUrl,
  variant,
}: {
  thumbnailUrl: string | null;
  variant?: number;
}) {
  return (
    <div className="aspect-video bg-gray-100 relative overflow-hidden">
      {thumbnailUrl ? (
        <img
          src={thumbnailUrl}
          alt=""
          className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform"
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 gap-2">
          <FileText className="w-8 h-8" />
          <span className="text-[10px] font-medium">WSR Deck</span>
        </div>
      )}
      {variant != null && variant > 0 ? (
        <VariantRibbon label={variantBadgeLabel(variant)} />
      ) : null}
    </div>
  );
}
function groupWeeks(weeks: WsrWeekSummary[]): WeekGroup[] {
  const map = new Map<string, WeekGroup>();

  for (const week of weeks) {
    const key = weekGroupKey(week.report_start_date, week.report_end_date);
    const existing = map.get(key);
    if (existing) {
      existing.variants.push(week);
    } else {
      map.set(key, {
        key,
        report_start_date: week.report_start_date,
        report_end_date: week.report_end_date,
        variants: [week],
      });
    }
  }

  return Array.from(map.values())
    .map((group) => ({
      ...group,
      variants: [...group.variants].sort(
        (a, b) => (a.variant ?? 1) - (b.variant ?? 1),
      ),
    }))
    .sort((a, b) => b.report_start_date.localeCompare(a.report_start_date));
}

function weekCardKey(week: WsrWeekSummary): string {
  return `${week.report_start_date}-${week.report_end_date}-v${week.variant ?? 1}`;
}

function getLatestVariant(group: WeekGroup): WsrWeekSummary {
  return [...group.variants].sort(
    (a, b) => new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime(),
  )[0];
}

function getFolderCoverImageUrl(group: WeekGroup): string | null {
  const latest = getLatestVariant(group);
  if (latest.template_id) {
    return wsrTemplateThumbnailUrl(latest.template_id);
  }
  return latest.thumbnail_url;
}

function VersionMeta({ week }: { week: WsrWeekSummary }) {
  return (
    <>
      <p className="text-xs text-gray-400 mt-1">
        Generated {formatGeneratedAt(week.generated_at)}
      </p>
      {week.template_name ? (
        <p className="text-[10px] text-gray-500 mt-2 truncate" title={week.template_name}>
          Template: {week.template_name}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2 mt-3">
        {week.slide_count > 0 ? (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-brand-red/10 text-brand-red">
            {week.slide_count} {week.slide_count === 1 ? "slide" : "slides"}
          </span>
        ) : null}
      </div>
      <p className="text-[10px] text-gray-400 mt-3 truncate" title={week.filename}>
        {week.filename}
      </p>
    </>
  );
}

export function ViewWSRPage() {
  const [weeks, setWeeks] = useState<WsrWeekSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<ViewMode>("list");
  const [selectedGroup, setSelectedGroup] = useState<WeekGroup | null>(null);
  const [disableTransition, setDisableTransition] = useState(false);
  const prevViewIndexRef = useRef(0);

  const [selectedDeck, setSelectedDeck] = useState<WsrWeekSummary | null>(null);
  // Kept for the slide-out transition so the panel does not go blank while closing.
  const [displayedDeck, setDisplayedDeck] = useState<WsrWeekSummary | null>(null);
  const [slideReviewOpen, setSlideReviewOpen] = useState(false);

  const weekGroups = useMemo(() => groupWeeks(weeks), [weeks]);
  const viewIndex = view === "list" ? 0 : view === "versions" ? 1 : 2;

  useEffect(() => {
    if (selectedDeck) {
      setDisplayedDeck(selectedDeck);
      return;
    }
    const timer = window.setTimeout(() => setDisplayedDeck(null), VIEW_TRANSITION_MS);
    return () => window.clearTimeout(timer);
  }, [selectedDeck]);

  const validation = useWsrValidation(
    displayedDeck?.report_start_date ?? "",
    displayedDeck?.report_end_date ?? "",
    displayedDeck?.variant ?? 1,
    displayedDeck != null,
  );

  // "Re-check deck": pull the latest SharePoint copy + re-validate (Slide Review stays a cached read).
  const recheck = useRecheckDeck({
    startDate: displayedDeck?.report_start_date ?? "",
    endDate: displayedDeck?.report_end_date ?? "",
    variant: displayedDeck?.variant ?? 1,
    templateId: displayedDeck?.template_id ?? null,
    fromSharepoint: Boolean(displayedDeck?.cloud_web_url),
    onRefresh: validation.refresh,
    onValidated: () => setSlideReviewOpen(true),
  });

  useEffect(() => {
    const jump = Math.abs(viewIndex - prevViewIndexRef.current);
    if (jump > 1) {
      setDisableTransition(true);
      const frame = window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => setDisableTransition(false));
      });
      prevViewIndexRef.current = viewIndex;
      return () => window.cancelAnimationFrame(frame);
    }
    prevViewIndexRef.current = viewIndex;
  }, [viewIndex]);

  const loadWeeks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchWsrWeeks();
      setWeeks(data.weeks);
    } catch (err) {
      setWeeks([]);
      setError(err instanceof Error ? err.message : "Failed to load WSR reports");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWeeks();
  }, [loadWeeks]);

  /** Open the deck detail panel (SharePoint / download links + Slide Review). */
  const openDeck = (deck: WsrWeekSummary) => {
    setSelectedDeck(deck);
    setSlideReviewOpen(false);
    setView("deck");
  };

  const openWeekGroup = (group: WeekGroup) => {
    setSelectedGroup(group);
    if (group.variants.length === 1) {
      // Single variant: open directly (no versions panel needed)
      openDeck(group.variants[0]);
      return;
    }
    // Multiple variants: show the versions panel so user can pick
    setView("versions");
  };

  const goBack = () => {
    if (view === "deck") {
      setSlideReviewOpen(false);
      setSelectedDeck(null);
      if (selectedGroup && selectedGroup.variants.length > 1) {
        setView("versions");
        return;
      }
      setSelectedGroup(null);
      setView("list");
      return;
    }
    if (view === "versions") {
      setSelectedGroup(null);
      setView("list");
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-brand-cream overflow-hidden">
      <div className="flex-1 min-h-0 overflow-hidden">
        <div
          className={`flex h-full ${disableTransition ? "" : "transition-transform duration-300 ease-in-out"}`}
          style={{
            width: `${VIEW_PANEL_COUNT * 100}%`,
            transform: `translateX(-${viewIndex * (100 / VIEW_PANEL_COUNT)}%)`,
          }}
        >
          {/* ── Panel 1: Week list ── */}
          <div className="w-1/3 h-full min-h-0 flex flex-col shrink-0">
            <div className="px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0">
              <h2 className="text-base font-semibold text-gray-800">View WSR Reports</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Browse previously generated weekly status decks. Click a week to open the deck, its
                SharePoint link and the slide review. Weeks with multiple templates appear as
                folders.
              </p>
            </div>

            <div className="flex-1 min-h-0 overflow-auto p-6">
              {loading && (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <Loader2 className="w-8 h-8 text-brand-red animate-spin mb-3" />
                  <p className="text-sm text-gray-600">Loading generated reports…</p>
                </div>
              )}

              {!loading && error && (
                <div className="max-w-lg mx-auto bg-red-50 border border-red-200 rounded-xl p-5">
                  <p className="text-sm font-semibold text-red-700">Could not load reports</p>
                  <p className="text-xs text-red-600 mt-2">{error}</p>
                  <button
                    type="button"
                    onClick={() => void loadWeeks()}
                    className="mt-4 text-xs font-semibold text-red-700 underline"
                  >
                    Retry
                  </button>
                </div>
              )}

              {!loading && !error && weekGroups.length === 0 && (
                <div className="max-w-lg mx-auto bg-white border border-gray-200 rounded-xl p-8 text-center shadow-sm">
                  <Presentation className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                  <p className="text-sm font-semibold text-gray-700">No WSR decks yet</p>
                  <p className="text-xs text-gray-400 mt-2">
                    Generate a report from{" "}
                    <span className="font-medium">Weekly Reports → Generate WSR</span> and it will
                    appear here.
                  </p>
                </div>
              )}

              {!loading && !error && weekGroups.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 max-w-6xl">
                  {weekGroups.map((group) => {
                    const isFolder = group.variants.length > 1;
                    const latestVariant = getLatestVariant(group);
                    const coverImageUrl = isFolder
                      ? getFolderCoverImageUrl(group)
                      : latestVariant.thumbnail_url;
                    const hasCloud = !isFolder && !!latestVariant.cloud_web_url;

                    return (
                      <button
                        key={group.key}
                        type="button"
                        onClick={() => openWeekGroup(group)}
                        className="text-left bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md hover:border-brand-red/30 transition-all group"
                      >
                        {/* Thumbnail (preserved for all levels) */}
                        <div className="aspect-video bg-gray-100 relative overflow-hidden">
                          {coverImageUrl ? (
                            <img
                              src={coverImageUrl}
                              alt=""
                              className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform"
                              loading="lazy"
                            />
                          ) : (
                            <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 gap-2">
                              {isFolder ? (
                                <FolderOpen className="w-9 h-9" />
                              ) : (
                                <FileText className="w-8 h-8" />
                              )}
                              <span className="text-[10px] font-medium">
                                {isFolder ? "WSR Folder" : "WSR Deck"}
                              </span>
                            </div>
                          )}
                          {isFolder ? (
                            <span className="absolute top-2 left-2 px-2 py-0.5 text-[10px] font-bold text-white rounded bg-brand-red flex items-center gap-1">
                              <FolderOpen className="w-3 h-3" />
                              {group.variants.length} decks
                            </span>
                          ) : null}
                          {/* SharePoint badge for single-variant cards with a cloud link */}
                          {hasCloud ? (
                            <span className="absolute top-2 right-2 px-2 py-0.5 text-[10px] font-bold text-white rounded bg-blue-600 flex items-center gap-1">
                              <ExternalLink className="w-3 h-3" />
                              SharePoint
                            </span>
                          ) : null}
                        </div>

                        <div className="p-4">
                          <p className="text-sm font-semibold text-gray-800 group-hover:text-brand-red transition-colors">
                            {formatWeekRange(group.report_start_date, group.report_end_date)}
                          </p>
                          {isFolder ? (
                            <p className="text-xs text-gray-400 mt-1">
                              {group.variants.length} WSR decks — click to pick a version
                            </p>
                          ) : (
                            <>
                              <VersionMeta week={latestVariant} />
                              {hasCloud ? (
                                <p className="text-[10px] text-blue-600 font-semibold mt-2 flex items-center gap-1">
                                  <ExternalLink className="w-3 h-3" />
                                  SharePoint link available
                                </p>
                              ) : (
                                <p className="text-[10px] text-gray-400 mt-2">
                                  No SharePoint link yet — download available
                                </p>
                              )}
                            </>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* ── Panel 2: Versions list for a week folder ── */}
          <div className="w-1/3 h-full min-h-0 flex flex-col shrink-0">
            <div className="px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={goBack}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 flex-shrink-0"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back
                </button>
                <div className="min-w-0">
                  <h2 className="text-base font-semibold text-gray-800 truncate">
                    {selectedGroup
                      ? formatWeekRange(
                          selectedGroup.report_start_date,
                          selectedGroup.report_end_date,
                        )
                      : "Week versions"}
                  </h2>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Select a version to open it and review its slides.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-auto p-6">
              {selectedGroup ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 max-w-6xl">
                  {selectedGroup.variants.map((week) => {
                    const variant = week.variant ?? 1;
                    const hasCloud = !!week.cloud_web_url;
                    return (
                      <button
                        key={weekCardKey(week)}
                        type="button"
                        onClick={() => openDeck(week)}
                        className="text-left bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md hover:border-brand-red/30 transition-all group"
                      >
                        {/* Thumbnail preserved at version level */}
                        <div className="relative">
                          <DeckThumbnail
                            thumbnailUrl={week.thumbnail_url}
                            variant={variant}
                          />
                          {hasCloud ? (
                            <span className="absolute top-2 right-2 px-2 py-0.5 text-[10px] font-bold text-white rounded bg-blue-600 flex items-center gap-1">
                              <ExternalLink className="w-3 h-3" />
                              SharePoint
                            </span>
                          ) : null}
                        </div>
                        <div className="p-4">
                          <p className="text-sm font-semibold text-gray-800 group-hover:text-brand-red transition-colors">
                            {formatWeekRange(week.report_start_date, week.report_end_date)}
                          </p>
                          <VersionMeta week={week} />
                          {hasCloud ? (
                            <p className="text-[10px] text-blue-600 font-semibold mt-2 flex items-center gap-1">
                              <ExternalLink className="w-3 h-3" />
                              SharePoint link available
                            </p>
                          ) : (
                            <p className="text-[10px] text-gray-400 mt-2">
                              No SharePoint link yet — download available
                            </p>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-center text-gray-400">
                  <FolderOpen className="w-10 h-10 mb-3" />
                  <p className="text-sm">No week selected</p>
                </div>
              )}
            </div>
          </div>

          {/* ── Panel 3: Deck details + Slide Review ── */}
          <div className="relative w-1/3 h-full min-h-0 flex flex-col shrink-0 overflow-hidden">
            {recheck.notice.message ? (
              <FloatingNotice
                message={recheck.notice.message}
                exiting={recheck.notice.exiting}
                onDismiss={recheck.notice.dismiss}
                tone={recheck.notice.tone}
                className="absolute top-4 left-1/2 z-50 w-[min(calc(100%-2rem),28rem)] -translate-x-1/2 text-xs"
              />
            ) : null}
            {displayedDeck ? (
              <>
                <div className="px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <button
                        type="button"
                        onClick={goBack}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 flex-shrink-0"
                      >
                        <ArrowLeft className="w-3.5 h-3.5" />
                        Back
                      </button>
                      <div className="min-w-0">
                        <h2 className="text-base font-semibold text-gray-800 truncate">
                          {formatWeekRange(
                            displayedDeck.report_start_date,
                            displayedDeck.report_end_date,
                          )}
                        </h2>
                        <p
                          className="text-xs text-gray-400 mt-0.5 truncate"
                          title={displayedDeck.filename}
                        >
                          {displayedDeck.filename}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {displayedDeck.cloud_web_url ? (
                        <a
                          href={displayedDeck.cloud_web_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-blue-200 text-blue-700 rounded-lg hover:bg-blue-50"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          SharePoint
                        </a>
                      ) : null}
                      <a
                        href={displayedDeck.download_url}
                        download={displayedDeck.filename}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-brand-orange rounded-lg hover:bg-brand-orange-hover"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </a>
                    </div>
                  </div>
                </div>

                <div className="flex-1 min-h-0 flex flex-col">
                  <WsrSlidePanel
                    key={weekCardKey(displayedDeck)}
                    startDate={displayedDeck.report_start_date}
                    endDate={displayedDeck.report_end_date}
                    variant={displayedDeck.variant ?? 1}
                    validation={validation}
                    open={slideReviewOpen}
                    onOpenChange={setSlideReviewOpen}
                    defaultContent={
                      <div className="flex-1 min-h-0 overflow-auto p-6">
                        <div className="max-w-md mx-auto text-center">
                          <div className="aspect-video bg-gray-100 rounded-xl overflow-hidden border border-gray-200 shadow-sm">
                            {displayedDeck.thumbnail_url ? (
                              <img
                                src={displayedDeck.thumbnail_url}
                                alt=""
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 gap-2">
                                <FileText className="w-8 h-8" />
                              </div>
                            )}
                          </div>
                          <p className="text-base font-semibold text-gray-800 mt-4">WSR Deck</p>
                          <p className="text-xs text-gray-500 mt-1">
                            {formatWeekRange(
                              displayedDeck.report_start_date,
                              displayedDeck.report_end_date,
                            )}
                          </p>
                          <div className="flex flex-wrap items-center justify-center gap-2 mt-5">
                            {displayedDeck.cloud_web_url ? (
                              <a
                                href={displayedDeck.cloud_web_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 shadow"
                              >
                                <ExternalLink className="w-4 h-4" />
                                Open in SharePoint
                              </a>
                            ) : null}
                            <a
                              href={displayedDeck.download_url}
                              download={displayedDeck.filename}
                              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-brand-orange rounded-lg hover:bg-brand-orange-hover shadow"
                            >
                              <Download className="w-4 h-4" />
                              Download PPT
                            </a>
                            <SlideReviewButton
                              onClick={() => setSlideReviewOpen(true)}
                              findingCount={validation.findingCount}
                              className="py-2 text-sm"
                            />
                            <RecheckDeckButton
                              onClick={() => void recheck.recheck()}
                              loading={recheck.rechecking}
                              disabled={validation.phase === "pending"}
                              className="py-2 text-sm"
                            />
                          </div>
                          {!displayedDeck.cloud_web_url ? (
                            <p className="mt-3 text-[11px] text-gray-400">
                              No SharePoint link yet — use Download PPT.
                            </p>
                          ) : null}
                        </div>
                      </div>
                    }
                  />
                </div>
              </>
            ) : view === "deck" ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-gray-400">
                <Loader2 className="w-8 h-8 text-brand-red animate-spin mb-3" />
                <p className="text-sm">Opening WSR deck…</p>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
