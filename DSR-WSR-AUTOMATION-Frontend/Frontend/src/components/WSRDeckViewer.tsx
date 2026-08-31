import { useEffect, useMemo, useState } from "react";
import type { WsrContentSection, WsrContentSlide } from "@/api/wsr";

const SLIDE_ACCENT = "#d3072a";
const SLIDE_HEADER_BG = "#202020";
const SLIDE_LIGHT_BG = "#f5f6ff";

const TRACK_TECH: Record<string, string> = {
  COST: "CHEDR (Haskell)",
  PRC: "Haskell and Java",
  LOC: "Java and Angular",
  SUP: "Java and Angular",
  SPUR: "Java and Angular",
  WNF: "Java",
  PHRM: "Java",
  GSS: "Java",
};

const TRACK_COLORS = [
  { bg: "#fde8ec", border: "#d3072a", num: "#d3072a" },
  { bg: "#f0fdf4", border: "#22c55e", num: "#15803d" },
  { bg: "#faf5ff", border: "#a855f7", num: "#7e22ce" },
  { bg: "#fff7ed", border: "#f97316", num: "#c2410c" },
  { bg: "#eff6ff", border: "#3b82f6", num: "#1d4ed8" },
  { bg: "#fdf2f8", border: "#ec4899", num: "#9d174d" },
  { bg: "#f0fdfa", border: "#14b8a6", num: "#0f766e" },
  { bg: "#fefce8", border: "#eab308", num: "#854d0e" },
];

interface DeckNavItem {
  slideNum: number;
  type: "index" | "track";
  label: string;
  slide?: WsrContentSlide;
}

function buildDeckNav(slides: WsrContentSlide[]): DeckNavItem[] {
  const nav: DeckNavItem[] = [{ slideNum: 1, type: "index", label: "Index" }];
  let num = 2;
  for (const slide of slides) {
    const label =
      slide.sections.length > 1
        ? `${slide.title} (${slide.sections.length} sprints)`
        : slide.title;
    nav.push({ slideNum: num++, type: "track", label, slide });
  }
  return nav;
}

function formatWeekLabel(start: string, end: string): string {
  const s = new Date(`${start}T00:00:00`);
  const e = new Date(`${end}T00:00:00`);
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return `${start} – ${end}`;
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  return `${fmt(s)} – ${fmt(e)}`;
}

function sectionTotals(section: WsrContentSection) {
  const completed = section.completed.length;
  const inprogress = section.inprogress.length;
  const released = section.released.length;
  const total = completed + inprogress + released;
  return { total, completed, inprogress, released };
}

function StoryList({
  title,
  items,
  dotClass,
}: {
  title: string;
  items: string[];
  dotClass: string;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1">
        <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotClass}`} />
        <span className="text-xs font-bold text-gray-700">
          {title} — {items.length} {items.length === 1 ? "story" : "stories"}
        </span>
      </div>
      {items.map((text, i) => (
        <div key={`${title}-${i}`} className="flex items-start gap-2 ml-3 text-gray-600 leading-snug py-0.5">
          <span className="flex-shrink-0 text-gray-300 mt-0.5">›</span>
          <span className="text-xs text-gray-600">{text}</span>
        </div>
      ))}
    </div>
  );
}

function SectionBlock({ section }: { section: WsrContentSection }) {
  const totals = sectionTotals(section);
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold text-gray-600">Sprint:</span>
        <span className="text-xs font-bold text-gray-800">{section.sprint_name}</span>
        {section.sprint_dates && (
          <>
            <span className="text-xs text-gray-400">·</span>
            <span className="text-xs text-gray-500">{section.sprint_dates}</span>
          </>
        )}
        <span className="text-xs text-gray-400">·</span>
        <span className="text-xs capitalize text-brand-red">{section.sprint_status}</span>
        {[
          { label: `${totals.total} Total`, color: "bg-gray-200 text-gray-700" },
          { label: `${totals.completed} Done`, color: "bg-green-100 text-green-700" },
          { label: `${totals.inprogress} In Progress`, color: "bg-blue-100 text-blue-700" },
          { label: `${totals.released} Released`, color: "bg-purple-100 text-purple-700" },
        ]
          .filter((c) => !c.label.startsWith("0 "))
          .map((chip) => (
            <span
              key={chip.label}
              className={`px-2 py-0.5 rounded-full text-xs font-semibold ${chip.color}`}
            >
              {chip.label}
            </span>
          ))}
      </div>

      <div className="rounded-lg overflow-hidden border border-brand-red/20">
        <div
          className="flex items-center gap-2 px-3 py-1.5 text-white text-xs font-semibold"
          style={{ background: SLIDE_ACCENT }}
        >
          Highlights
        </div>
        <div className="px-3 py-2 space-y-2" style={{ background: SLIDE_LIGHT_BG }}>
          <StoryList title="Completed this week" items={section.completed} dotClass="bg-green-500" />
          <StoryList title="In progress" items={section.inprogress} dotClass="bg-brand-red/100" />
          <StoryList title="Released" items={section.released} dotClass="bg-purple-500" />
          {totals.total === 0 && (
            <p className="text-xs text-gray-400 italic">No stories in this sprint section</p>
          )}
        </div>
      </div>
    </div>
  );
}

function DeckIndexSlide({
  nav,
  weekLabel,
}: {
  nav: DeckNavItem[];
  weekLabel: string;
}) {
  const trackEntries = nav.filter((n) => n.type === "track");
  return (
    <div className="w-full h-full flex flex-col" style={{ fontFamily: "Inter, sans-serif", background: "#f8f9fc" }}>
      <div className="flex items-center justify-between px-8 py-5" style={{ background: SLIDE_HEADER_BG }}>
        <div>
          <p className="text-white/50 text-xs font-medium uppercase tracking-widest mb-0.5">
            Weekly Status Report
          </p>
          <h1 className="text-white text-xl font-bold tracking-tight">Track Index</h1>
        </div>
        <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
          <div className="w-2 h-2 rounded-full bg-brand-red/70" />
          <span className="text-white/70 text-xs font-medium">{weekLabel}</span>
        </div>
      </div>
      <div className="px-8 py-2.5 bg-white border-b border-gray-100">
        <span className="text-xs text-gray-400">
          Navigate to any track section using the slide list on the left
        </span>
      </div>
      <div className="flex-1 px-8 py-6 flex items-center">
        <div className="grid grid-cols-4 gap-4 w-full">
          {trackEntries.map((entry, i) => {
            const colors = TRACK_COLORS[i % TRACK_COLORS.length];
            const tech = entry.slide
              ? TRACK_TECH[entry.slide.project_key] ?? ""
              : "";
            return (
              <div
                key={entry.slideNum}
                className="rounded-xl border-2 flex flex-col overflow-hidden"
                style={{ background: colors.bg, borderColor: colors.border }}
              >
                <div className="flex items-center justify-between px-3 pt-3 pb-1">
                  <span className="text-3xl font-black leading-none" style={{ color: colors.num }}>
                    {String(entry.slideNum).padStart(2, "0")}
                  </span>
                </div>
                <div className="px-3 pb-3 flex-1 flex flex-col justify-end">
                  <p className="text-xs font-bold text-gray-800 leading-snug">{entry.label}</p>
                  {tech && <p className="text-xs text-gray-400 mt-0.5 leading-tight">{tech}</p>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function DeckTrackSlide({
  slide,
  reportStart,
  reportEnd,
}: {
  slide: WsrContentSlide;
  reportStart: string;
  reportEnd: string;
}) {
  const tech = TRACK_TECH[slide.project_key] ?? "";
  const primary = slide.sections[0];
  const sprintDates = primary?.sprint_dates ?? formatWeekLabel(reportStart, reportEnd);
  const totals = slide.sections.reduce(
    (acc, s) => {
      const t = sectionTotals(s);
      return {
        total: acc.total + t.total,
        completed: acc.completed + t.completed,
        inprogress: acc.inprogress + t.inprogress,
        released: acc.released + t.released,
      };
    },
    { total: 0, completed: 0, inprogress: 0, released: 0 },
  );

  return (
    <div
      className="w-full h-full flex flex-col overflow-hidden bg-[#f8f9fc]"
      style={{ fontFamily: "Inter, sans-serif", fontSize: "11px" }}
    >
      <div
        className="flex items-center justify-between px-5 py-3 flex-shrink-0"
        style={{ background: SLIDE_HEADER_BG }}
      >
        <div className="min-w-0">
          <p className="text-sm font-bold text-white block">
            Delivery Status — {slide.title}
          </p>
          <p className="text-xs text-white/50 mt-0.5 block">
            Week {sprintDates}
            {tech ? `  ·  Tech: ${tech}` : ""}
          </p>
        </div>
        <div className="flex-shrink-0 ml-4 bg-white/10 rounded-lg px-3 py-1.5 text-white/70 text-xs font-medium whitespace-nowrap">
          {reportStart} – {reportEnd}
        </div>
      </div>
      <div className="h-0.5 flex-shrink-0" style={{ background: SLIDE_ACCENT }} />

      <div className="flex flex-1 min-h-0 p-3 gap-3 overflow-auto">
        <div className="flex-1 flex flex-col gap-2.5 min-w-0">
          {slide.sections.map((section, i) => (
            <SectionBlock key={`${section.sprint_name}-${i}`} section={section} />
          ))}

          <div className="rounded-lg overflow-hidden border border-brand-red/20">
            <div
              className="flex items-center gap-2 px-3 py-1.5 text-white text-xs font-semibold"
              style={{ background: "#d94809" }}
            >
              Key Activities for Next Week
            </div>
            <div className="px-3 py-2 space-y-1" style={{ background: SLIDE_LIGHT_BG }}>
              {slide.key_activities.length > 0 ? (
                slide.key_activities.map((item, i) => (
                  <div key={i} className="flex items-start gap-2 text-gray-600 leading-snug">
                    <span className="w-4 h-4 rounded-full bg-brand-red/10 text-brand-red flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5">
                      {i + 1}
                    </span>
                    <span className="text-xs text-gray-600">{item}</span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-gray-400 italic">Reserved for manual BSA entry</p>
              )}
            </div>
          </div>
        </div>

        <div className="w-32 flex-shrink-0 flex flex-col gap-2">
          <div className="rounded-lg overflow-hidden border border-brand-red/20">
            <div
              className="text-center text-white text-xs font-semibold py-1"
              style={{ background: SLIDE_ACCENT }}
            >
              Sprint Stats
            </div>
            <div className="p-2 space-y-1.5 bg-gray-50">
              {[
                { label: "Total", val: totals.total, tw: "bg-gray-500" },
                { label: "Done", val: totals.completed, tw: "bg-green-500" },
                { label: "In Progress", val: totals.inprogress, tw: "bg-brand-red/100" },
                { label: "Released", val: totals.released, tw: "bg-purple-500" },
              ].map((row) => (
                <div key={row.label} className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-sm flex-shrink-0 ${row.tw}`} />
                  <span className="text-xs text-gray-500 flex-1 truncate">{row.label}</span>
                  <span className="text-xs font-bold text-gray-800">{row.val}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface WSRDeckViewerProps {
  slides: WsrContentSlide[];
  reportStartDate: string;
  reportEndDate: string;
}

export function WSRDeckViewer({
  slides,
  reportStartDate,
  reportEndDate,
}: WSRDeckViewerProps) {
  const nav = useMemo(() => buildDeckNav(slides), [slides]);
  const [activeSlide, setActiveSlide] = useState(1);
  const current = nav.find((s) => s.slideNum === activeSlide) ?? nav[0];
  const weekLabel = formatWeekLabel(reportStartDate, reportEndDate);

  useEffect(() => {
    setActiveSlide(1);
  }, [reportStartDate, reportEndDate, slides]);

  if (slides.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-500">
        No track slides in this report.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <div className="w-52 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-3 py-3 border-b border-gray-100 bg-gray-50">
          <p className="text-xs font-bold text-gray-700 uppercase tracking-wide">Slides</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {nav.length} slides · {slides.length} tracks
          </p>
        </div>
        <div className="flex-1 overflow-y-auto py-1">
          {nav.map((slide) => (
            <button
              key={slide.slideNum}
              type="button"
              onClick={() => setActiveSlide(slide.slideNum)}
              className={`w-full flex items-start gap-2.5 px-3 py-2 text-left transition-colors hover:bg-brand-red/10 ${
                activeSlide === slide.slideNum
                  ? "bg-brand-red/10 border-l-2 border-brand-red"
                  : "border-l-2 border-transparent"
              }`}
            >
              <span
                className={`text-xs font-bold flex-shrink-0 mt-0.5 w-5 text-right ${
                  activeSlide === slide.slideNum ? "text-brand-red" : "text-gray-400"
                }`}
              >
                {String(slide.slideNum).padStart(2, "0")}
              </span>
              <span
                className={`text-xs leading-snug ${
                  activeSlide === slide.slideNum
                    ? "text-brand-red font-semibold"
                    : "text-gray-600"
                }`}
              >
                {slide.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0 bg-gray-200">
        <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveSlide(Math.max(1, activeSlide - 1))}
              disabled={activeSlide === 1}
              className="px-3 py-1.5 text-xs border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 font-medium"
            >
              ← Prev
            </button>
            <span className="text-xs text-gray-500 font-medium">
              Slide {activeSlide} / {nav.length}
            </span>
            <button
              type="button"
              onClick={() => setActiveSlide(Math.min(nav.length, activeSlide + 1))}
              disabled={activeSlide === nav.length}
              className="px-3 py-1.5 text-xs border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 font-medium"
            >
              Next →
            </button>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-6 overflow-auto">
          <div
            className="bg-white shadow-2xl rounded overflow-hidden w-full"
            style={{ maxWidth: "900px", aspectRatio: "16/9" }}
          >
            {current.type === "index" ? (
              <DeckIndexSlide nav={nav} weekLabel={weekLabel} />
            ) : current.slide ? (
              <DeckTrackSlide
                slide={current.slide}
                reportStart={reportStartDate}
                reportEnd={reportEndDate}
              />
            ) : null}
          </div>
        </div>
        <div className="px-4 py-2 bg-white border-t border-gray-200 flex items-center gap-2">
          <span className="text-xs font-bold text-gray-400">#{activeSlide}</span>
          <span className="text-xs text-gray-600 font-medium">{current.label}</span>
        </div>
      </div>
    </div>
  );
}
