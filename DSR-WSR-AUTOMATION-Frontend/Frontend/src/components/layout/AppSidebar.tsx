import { useCallback, useRef, useState, type ReactNode } from "react";
import { ChevronDown, Ticket, Upload } from "lucide-react";
import g10xLogo from "@/assets/g10x-logo.png";

type AppPage = "intake" | "complete-stories" | "view-dsr" | "wsr-generate" | "wsr-view";

interface DsrTrack {
  id: string;
  name: string;
}

interface AppSidebarProps {
  page: AppPage;
  setPage: (page: AppPage) => void;
  dsrOpen: boolean;
  setDsrOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  wsrOpen: boolean;
  setWsrOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  selectedDsrTrackId: string | undefined;
  setSelectedDsrTrackId: (id: string) => void;
  dsrTrackList: DsrTrack[];
  onRefreshTracks: () => void;
}

const COLLAPSE_DELAY_MS = 400;
const MINI_WIDTH = "3.5rem";
const EXPANDED_WIDTH = "14rem";
const ICON_COL_WIDTH = "3.5rem";
const NAV_ITEM_HEIGHT = "2.5rem";
const SUB_ITEM_HEIGHT = "2.5rem";
const DSR_TRACKS_MAX_HEIGHT = "max-h-60";

/** Vertical guide aligned under the parent nav icon column. */
const submenuContainerClass =
  "mt-1 ml-[calc(3.5rem-1px)] border-l border-white/10 pl-3";

const subItemClass = (active: boolean) =>
  `flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${SUB_ITEM_HEIGHT} ${
    active
      ? "bg-brand-red text-white"
      : "text-white/50 hover:bg-white/10 hover:text-white"
  }`;

export function AppSidebar({
  page,
  setPage,
  dsrOpen,
  setDsrOpen,
  wsrOpen,
  setWsrOpen,
  selectedDsrTrackId,
  setSelectedDsrTrackId,
  dsrTrackList,
  onRefreshTracks,
}: AppSidebarProps) {
  const [expanded, setExpanded] = useState(false);
  const collapseTimerRef = useRef<number | null>(null);

  const clearCollapseTimer = useCallback(() => {
    if (collapseTimerRef.current != null) {
      window.clearTimeout(collapseTimerRef.current);
      collapseTimerRef.current = null;
    }
  }, []);

  const expandSidebar = useCallback(() => {
    clearCollapseTimer();
    setExpanded(true);
  }, [clearCollapseTimer]);

  const scheduleCollapse = useCallback(() => {
    clearCollapseTimer();
    collapseTimerRef.current = window.setTimeout(() => {
      setExpanded(false);
      collapseTimerRef.current = null;
    }, COLLAPSE_DELAY_MS);
  }, [clearCollapseTimer]);

  const navBtnClass = (active: boolean) =>
    `flex w-full items-center rounded-lg text-sm font-medium transition-colors ${NAV_ITEM_HEIGHT} ${
      active
        ? "bg-brand-red text-white"
        : "text-white/60 hover:bg-white/10 hover:text-white"
    }`;

  const labelClass = (extra = "") =>
    `min-w-0 flex-1 truncate text-left transition-opacity duration-200 ${
      expanded
        ? "opacity-100"
        : "max-w-0 flex-none overflow-hidden opacity-0"
    } ${extra}`;

  const submenuShellClass = (open: boolean) =>
    `grid transition-[grid-template-rows,opacity] duration-200 ease-out ${
      expanded && open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
    }`;

  const iconSlot = (node: ReactNode) => (
    <span
      className="flex flex-shrink-0 items-center justify-center"
      style={{ width: ICON_COL_WIDTH, height: NAV_ITEM_HEIGHT }}
    >
      {node}
    </span>
  );

  return (
    <>
      <div
        className="fixed left-0 top-0 bottom-0 z-50 w-2"
        onMouseEnter={expandSidebar}
        aria-hidden
      />

      <aside
        className="relative z-40 flex h-screen flex-shrink-0 flex-col overflow-hidden bg-brand-black transition-[width] duration-200 ease-out"
        style={{ width: expanded ? EXPANDED_WIDTH : MINI_WIDTH }}
        onMouseEnter={expandSidebar}
        onMouseLeave={scheduleCollapse}
      >
        {/* Logo — fixed height; icon column stays aligned with nav icons */}
        <div className="flex h-16 flex-shrink-0 items-center border-b border-white/10">
          <span
            className="flex flex-shrink-0 items-center justify-center"
            style={{ width: ICON_COL_WIDTH, height: "4rem" }}
          >
            <img
              src={g10xLogo}
              alt="G10X"
              className="h-9 w-9 object-contain"
              title="G10X"
            />
          </span>
          <div
            className={`min-w-0 overflow-hidden pr-3 transition-[opacity,max-width] duration-200 ${
              expanded
                ? "max-w-[10rem] opacity-100"
                : "max-w-0 flex-none opacity-0"
            }`}
          >
            <p className="truncate text-sm font-bold leading-tight text-white">
              HEB Status Tracker
            </p>
            <p className="text-xs leading-tight text-white/40">DSR · WSR</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto overflow-x-hidden py-4 spotlight-scroll [scrollbar-gutter:stable]">
          <button
            type="button"
            title="Intake Portal"
            onClick={() => setPage("intake")}
            className={navBtnClass(page === "intake")}
          >
            {iconSlot(<Upload className="h-4 w-4 flex-shrink-0" />)}
            <span className={labelClass()}>Intake Portal</span>
          </button>

          <button
            type="button"
            title="Story Board"
            onClick={() => setPage("complete-stories")}
            className={navBtnClass(page === "complete-stories")}
          >
            {iconSlot(<Ticket className="h-4 w-4 flex-shrink-0" />)}
            <span className={labelClass()}>Story Board</span>
          </button>

          <div>
            <button
              type="button"
              title="View Daily Status Report"
              onClick={() => {
                if (!expanded) {
                  expandSidebar();
                  setDsrOpen(true);
                  onRefreshTracks();
                  return;
                }
                setDsrOpen((o) => {
                  const opening = !o;
                  if (opening) onRefreshTracks();
                  return opening;
                });
              }}
              className={navBtnClass(page === "view-dsr")}
            >
              {iconSlot(
                <svg
                  className="h-4 w-4 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  />
                </svg>,
              )}
              <span className={labelClass("text-xs leading-tight")}>
                View Daily Status Report
              </span>
              <ChevronDown
                className={`h-3.5 w-3.5 flex-shrink-0 transition-all duration-200 ${
                  expanded
                    ? "mr-2 opacity-100"
                    : "mr-0 w-0 overflow-hidden opacity-0"
                } ${dsrOpen || page === "view-dsr" ? "rotate-180" : ""}`}
              />
            </button>

            <div className={submenuShellClass(dsrOpen || page === "view-dsr")}>
              <div className="min-h-0 overflow-hidden">
                <div className={submenuContainerClass}>
                  <div
                    className={`space-y-0.5 overflow-y-auto overflow-x-hidden spotlight-scroll [scrollbar-gutter:stable] ${DSR_TRACKS_MAX_HEIGHT}`}
                  >
                {dsrTrackList.map((track) => (
                  <button
                    key={track.id}
                    type="button"
                    onClick={() => {
                      setSelectedDsrTrackId(track.id);
                      setPage("view-dsr");
                      setDsrOpen(true);
                      onRefreshTracks();
                    }}
                    className={subItemClass(
                      page === "view-dsr" && selectedDsrTrackId === track.id,
                    )}
                  >
                    {track.name}
                  </button>
                ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div>
            <button
              type="button"
              title="Weekly Reports"
              onClick={() => {
                if (!expanded) {
                  expandSidebar();
                  setWsrOpen(true);
                  return;
                }
                setWsrOpen((o) => !o);
              }}
              className={navBtnClass(page === "wsr-generate" || page === "wsr-view")}
            >
              {iconSlot(
                <svg
                  className="h-4 w-4 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>,
              )}
              <span className={labelClass()}>Weekly Reports</span>
              <ChevronDown
                className={`h-3.5 w-3.5 flex-shrink-0 transition-all duration-200 ${
                  expanded
                    ? "mr-2 opacity-100"
                    : "mr-0 w-0 overflow-hidden opacity-0"
                } ${
                  wsrOpen || page === "wsr-generate" || page === "wsr-view"
                    ? "rotate-180"
                    : ""
                }`}
              />
            </button>

            <div
              className={submenuShellClass(
                wsrOpen || page === "wsr-generate" || page === "wsr-view",
              )}
            >
              <div className="min-h-0 overflow-hidden">
                <div className={`${submenuContainerClass} space-y-0.5`}>
                <button
                  type="button"
                  onClick={() => {
                    setPage("wsr-generate");
                    setWsrOpen(true);
                  }}
                  className={subItemClass(page === "wsr-generate")}
                >
                  <svg
                    className="h-3.5 w-3.5 flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                  Generate WSR
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPage("wsr-view");
                    setWsrOpen(true);
                  }}
                  className={subItemClass(page === "wsr-view")}
                >
                  <svg
                    className="h-3.5 w-3.5 flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 6h16M4 10h16M4 14h16M4 18h16"
                    />
                  </svg>
                  View WSR
                </button>
                </div>
              </div>
            </div>
          </div>
        </nav>
      </aside>
    </>
  );
}
