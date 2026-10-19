import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ExternalLink, FileText, FolderOpen, Loader2, Presentation } from "lucide-react";
import { fetchWsrWeeks, wsrTemplateThumbnailUrl, type WsrWeekSummary } from "@/api/wsr";
// import { WSRReportPanel } from "@/components/WSRReportPanel"; // MIGHT BE USED IN FUTURE — in-browser deck viewer
import { VariantRibbon, variantBadgeLabel } from "@/components/wsr/VariantRibbon";

// "deck" view mode is commented out — WSR decks now open directly in SharePoint.
// MIGHT BE USED IN FUTURE for in-browser deck viewing.
// type ViewMode = "list" | "versions" | "deck";
type ViewMode = "list" | "versions";

// VIEW_PANEL_COUNT was 3 (list + versions + deck). Now only 2 panels are active.
// MIGHT BE USED IN FUTURE if the deck panel is re-enabled.
// const VIEW_PANEL_COUNT = 3;
const VIEW_PANEL_COUNT = 2;
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

  // MIGHT BE USED IN FUTURE — selectedDeck / displayedDeck states for in-browser deck panel
  // const [selectedDeck, setSelectedDeck] = useState<WsrWeekSummary | null>(null);
  // const [displayedDeck, setDisplayedDeck] = useState<WsrWeekSummary | null>(null);

  const weekGroups = useMemo(() => groupWeeks(weeks), [weeks]);
  const viewIndex = view === "list" ? 0 : 1;

  // MIGHT BE USED IN FUTURE — displayedDeck fade-out timer for deck panel transition
  // useEffect(() => {
  //   if (selectedDeck) { setDisplayedDeck(selectedDeck); return; }
  //   const timer = window.setTimeout(() => setDisplayedDeck(null), VIEW_TRANSITION_MS);
  //   return () => window.clearTimeout(timer);
  // }, [selectedDeck]);

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

  /**
   * Open a deck directly in SharePoint (or download fallback).
   * If a cloud_web_url is available, opens in a new tab.
   * MIGHT BE USED IN FUTURE: previously navigated to the in-browser deck panel.
   */
  const openDeck = (deck: WsrWeekSummary) => {
    if (deck.cloud_web_url) {
      window.open(deck.cloud_web_url, "_blank", "noopener,noreferrer");
    } else {
      // Fallback: download the PPT file directly
      window.open(deck.download_url, "_blank", "noopener,noreferrer");
    }
    // MIGHT BE USED IN FUTURE — navigate into in-browser deck panel:
    // setSelectedDeck(deck);
    // setView("deck");
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
    // MIGHT BE USED IN FUTURE — "deck" view back logic:
    // if (view === "deck") {
    //   if (selectedGroup && selectedGroup.variants.length > 1) {
    //     setSelectedDeck(null); setView("versions"); return;
    //   }
    //   setSelectedGroup(null); setSelectedDeck(null); setView("list"); return;
    // }
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
          <div className="w-1/2 h-full min-h-0 flex flex-col shrink-0">
            <div className="px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0">
              <h2 className="text-base font-semibold text-gray-800">View WSR Reports</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Browse previously generated weekly status decks. Click a single-variant week to open
                it directly in SharePoint. Weeks with multiple templates appear as folders.
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
                                  Opens in SharePoint
                                </p>
                              ) : (
                                <p className="text-[10px] text-gray-400 mt-2">
                                  Opens as download (no cloud link yet)
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
          <div className="w-1/2 h-full min-h-0 flex flex-col shrink-0">
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
                    Select a version — it will open directly in SharePoint.
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
                              Opens in SharePoint
                            </p>
                          ) : (
                            <p className="text-[10px] text-gray-400 mt-2">
                              Opens as download (no cloud link yet)
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

          {/*
           * MIGHT BE USED IN FUTURE — Deck viewer panel (in-browser PPT slide viewer)
           * Previously the 3rd panel that rendered WSRReportPanel in "viewer" mode with
           * slide thumbnails on the left and the active slide on the right.
           *
           * To re-enable:
           *  1. Restore ViewMode = "list" | "versions" | "deck"
           *  2. Restore VIEW_PANEL_COUNT = 3 and w-1/3 on panels
           *  3. Restore selectedDeck / displayedDeck state
           *  4. Restore openDeck() to set selectedDeck + setView("deck")
           *  5. Uncomment import { WSRReportPanel } at the top
           *  6. Uncomment the panel below
           *
           * <div className="w-1/3 h-full min-h-0 flex flex-col shrink-0 overflow-hidden">
           *   {deckToShow ? (
           *     <WSRReportPanel
           *       key={weekCardKey(deckToShow)}
           *       startDate={deckToShow.report_start_date}
           *       endDate={deckToShow.report_end_date}
           *       variant={deckToShow.variant ?? 1}
           *       mode="viewer"
           *       autoGenerate={false}
           *       showRegenerate={false}
           *       onBack={goBack}
           *     />
           *   ) : view === "deck" ? (
           *     <div className="flex flex-col items-center justify-center h-full text-center text-gray-400">
           *       <Loader2 className="w-8 h-8 text-brand-red animate-spin mb-3" />
           *       <p className="text-sm">Opening WSR deck…</p>
           *     </div>
           *   ) : null}
           * </div>
           */}
        </div>
      </div>
    </div>
  );
}
