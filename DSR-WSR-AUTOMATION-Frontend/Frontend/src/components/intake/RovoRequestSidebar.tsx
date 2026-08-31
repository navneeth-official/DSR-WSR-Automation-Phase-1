import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, Copy } from "lucide-react";
import { isCatalogTrackActive, type TrackListItem } from "@/api/dsr";
import { fetchEmployeesByTeam, type EmployeeTrackItem } from "@/api/employees";
import { buildRovoRequestText, formatActivityDatePhrase, isoDate } from "@/lib/trackAssignees";
import { AssigneeEditorPanel } from "./AssigneeEditorPanel";
import { TrackEditorPanel } from "./TrackEditorPanel";
import { DateRangePicker } from "./DateRangePicker";
import { FloatingNotice, useFloatingNotice } from "@/components/ui/FloatingNotice";

const DEFAULT_TEAM = "HEB";

type SidebarTab = "rovo" | "assignees" | "tracks";

const TAB_CONFIG: { id: SidebarTab; label: string; subtitle: string }[] = [
  {
    id: "rovo",
    label: "Rovo request format",
    subtitle: "All active assignees across tracks",
  },
  {
    id: "assignees",
    label: "Create / edit assignees",
    subtitle: "Create or edit track assignments",
  },
  {
    id: "tracks",
    label: "Add new tracks",
    subtitle: "Create tracks or update status",
  },
];

function getMondayOf(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function getFridayOf(monday: Date): Date {
  const d = new Date(monday);
  d.setDate(d.getDate() + 4);
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Unique employee names with at least one active assignment on an active track. */
function uniqueActiveAssigneeNames(
  rows: Pick<EmployeeTrackItem, "employee_name" | "is_active" | "project_id">[],
  trackCatalog: TrackListItem[],
): string[] {
  const activeTrackIds = new Set(
    trackCatalog.filter(isCatalogTrackActive).map((t) => t.project_id),
  );
  const seen = new Set<string>();
  const out: string[] = [];
  for (const row of rows) {
    if (!row.is_active) continue;
    if (!activeTrackIds.has(row.project_id)) continue;
    const name = row.employee_name.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    out.push(name);
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function VerticalTabRail({
  activeTab,
  open,
  onSelectTab,
}: {
  activeTab: SidebarTab;
  open: boolean;
  onSelectTab: (tab: SidebarTab) => void;
}) {
  return (
    <div
      className={`flex flex-col flex-shrink-0 overflow-hidden bg-brand-black border border-brand-black ${
        open
          ? "rounded-l-lg border-r-0 shadow-[-6px_0_18px_rgba(0,0,0,0.35)]"
          : "rounded-l-lg shadow-[0_0_0_1px_rgba(0,0,0,0.2),_-8px_0_24px_rgba(0,0,0,0.25),_0_8px_20px_rgba(0,0,0,0.15)]"
      }`}
    >
      {TAB_CONFIG.map((tab) => {
        const isActive = open && activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onSelectTab(tab.id)}
            title={tab.label}
            className={`flex items-center justify-center px-2.5 py-5 transition-colors border-b border-white/10 last:border-b-0 ${
              isActive
                ? "bg-brand-red text-white"
                : "bg-brand-black text-white/70 hover:bg-white/10 hover:text-white"
            }`}
          >
            <span
              className="text-[11px] font-semibold leading-none tracking-wide"
              style={{ writingMode: "vertical-lr" }}
            >
              {tab.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function RovoPanel({
  assignees,
  employeesLoading,
  employeesError,
  activityStart,
  activityEnd,
  onDateChange,
  snapshotIso,
}: {
  assignees: string[];
  employeesLoading: boolean;
  employeesError: string;
  activityStart: Date | null;
  activityEnd: Date | null;
  onDateChange: (start: Date | null, end: Date | null) => void;
  snapshotIso: string;
}) {
  const activityStartIso = activityStart ? isoDate(activityStart) : "YYYY-MM-DD";
  const activityEndIso = activityEnd ? isoDate(activityEnd) : "YYYY-MM-DD";
  const activityPhrase = formatActivityDatePhrase(activityStartIso, activityEndIso);

  return (
    <div className="text-xs text-gray-700 leading-relaxed space-y-4">
      <section>
        <p className="font-medium text-gray-800 mb-2">
          Retrieve all Jira issues assigned to:
        </p>
        {employeesLoading ? (
          <p className="text-gray-400 mb-2">Loading assignees…</p>
        ) : employeesError ? (
          <p className="text-red-500 mb-2">{employeesError}</p>
        ) : assignees.length === 0 ? (
          <p className="text-gray-400 mb-2">
            No active assignees found. Use the Assignees tab to add one, or run{" "}
            <code className="text-[10px] bg-gray-100 px-1 rounded">
              backfill_employees_from_stories.py
            </code>
            .
          </p>
        ) : (
          <ul className="space-y-1 mb-2">
            {assignees.map((name) => (
              <li key={name} className="flex gap-2 text-gray-700">
                <span className="text-gray-400 flex-shrink-0">*</span>
                <span>{name}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <p className="mb-2">
          Include issues where any of the following occurred{" "}
          {activityPhrase.preposition}
        </p>
        <DateRangePicker
          start={activityStart}
          end={activityEnd}
          onChange={onDateChange}
        />
        <ul className="mt-3 space-y-0.5 text-gray-600 list-none pl-0">
          {[
            "Issue created",
            "Issue updated",
            "Status transitioned",
            "Assignee changed",
            "Sprint changed",
            "Issue resolved",
          ].map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-gray-400">*</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <p className="font-medium text-gray-800 mb-2">
          For each issue return the following fields exactly as shown:
        </p>
        <pre className="text-[10px] font-mono bg-gray-900 text-green-400 rounded-lg p-3 overflow-x-auto leading-snug">
{`{
  "project_key": "",
  "project_name": "",
  "sprint_name": "",
  "sprint_start_date": "",
  "sprint_end_date": "",
  "jira_key": "",
  "summary": "",
  "description": "",
  "issue_type": "",
  "priority": "",
  "assignee": "",
  "reporter": "",
  "status": "",
  "story_points": 0,
  "created_date": "",
  "updated_date": "",
  "resolved_date": "",
  "snapshot_date": ""
}`}
        </pre>
      </section>

      <section>
        <p className="font-medium text-gray-800 mb-2">Rules:</p>
        <ol className="space-y-1.5 text-gray-600 list-none pl-0">
          <li>1. Return one JSON object per Jira issue.</li>
          <li>2. Include active and closed sprint information when available.</li>
          <li>3. Include completed and incomplete issues.</li>
          <li>4. Use null for unavailable values.</li>
          <li>5. Set snapshot_date to today&apos;s date ({snapshotIso}).</li>
          <li className="flex flex-wrap items-center gap-2">
            <span>6. Return only issues modified {activityPhrase.preposition}</span>
            <DateRangePicker
              start={activityStart}
              end={activityEnd}
              onChange={onDateChange}
            />
          </li>
          <li>7. Output must be valid JSON.</li>
        </ol>
      </section>
    </div>
  );
}

export function RovoRequestSidebar({
  trackCatalog,
  onTracksChanged,
}: {
  trackCatalog: TrackListItem[];
  onTracksChanged: () => void;
}) {
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const defaultMonday = useMemo(() => getMondayOf(today), [today]);
  const defaultFriday = useMemo(() => getFridayOf(defaultMonday), [defaultMonday]);

  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<SidebarTab>("rovo");
  const [employeeRows, setEmployeeRows] = useState<EmployeeTrackItem[]>([]);
  const [activityStart, setActivityStart] = useState<Date | null>(defaultMonday);
  const [activityEnd, setActivityEnd] = useState<Date | null>(defaultFriday);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [employeesError, setEmployeesError] = useState("");
  const [copyHint, setCopyHint] = useState("");
  const sidebarRootRef = useRef<HTMLDivElement>(null);
  const {
    message: sidebarNotice,
    exiting: sidebarNoticeExiting,
    show: showSidebarNotice,
    dismiss: dismissSidebarNotice,
  } = useFloatingNotice();
  const [employeeRefreshKey, setEmployeeRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setEmployeesLoading(true);
    setEmployeesError("");

    void fetchEmployeesByTeam(DEFAULT_TEAM, { activeOnly: true })
      .then((response) => {
        if (cancelled) return;
        setEmployeeRows(response.employees);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setEmployeesError(
          err instanceof Error ? err.message : "Failed to load employees",
        );
        setEmployeeRows([]);
      })
      .finally(() => {
        if (!cancelled) setEmployeesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [employeeRefreshKey]);

  const assignees = useMemo(
    () => uniqueActiveAssigneeNames(employeeRows, trackCatalog),
    [employeeRows, trackCatalog],
  );

  const handleAssigneeChanged = useCallback(
    (message?: string) => {
      setEmployeeRefreshKey((k) => k + 1);
      if (message) {
        showSidebarNotice(message);
      }
    },
    [showSidebarNotice],
  );

  const handleTracksChanged = useCallback(
    (message?: string) => {
      onTracksChanged();
      setEmployeeRefreshKey((k) => k + 1);
      if (message) {
        showSidebarNotice(message);
      }
    },
    [onTracksChanged, showSidebarNotice],
  );

  const activityStartIso = activityStart ? isoDate(activityStart) : "YYYY-MM-DD";
  const activityEndIso = activityEnd ? isoDate(activityEnd) : "YYYY-MM-DD";
  const snapshotIso = isoDate(today);

  const requestText = buildRovoRequestText({
    assignees,
    activityStart: activityStartIso,
    activityEnd: activityEndIso,
    snapshotDate: snapshotIso,
  });

  const copyRequest = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(requestText);
      setCopyHint("Copied!");
      setTimeout(() => setCopyHint(""), 2000);
    } catch {
      setCopyHint("Copy failed");
      setTimeout(() => setCopyHint(""), 2000);
    }
  }, [requestText]);

  const selectTab = (tab: SidebarTab) => {
    setActiveTab(tab);
    setOpen(true);
  };

  const activeConfig = TAB_CONFIG.find((t) => t.id === activeTab) ?? TAB_CONFIG[0];

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      const root = sidebarRootRef.current;
      if (root && !root.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  return (
    <div className="fixed top-0 bottom-0 right-0 z-40 flex items-center pointer-events-none">
      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-30 cursor-default bg-black/10 pointer-events-auto"
          aria-label="Close sidebar"
          onClick={() => setOpen(false)}
        />
      ) : null}

      <div ref={sidebarRootRef} className="relative z-40 flex items-center h-full pointer-events-auto">
        <VerticalTabRail activeTab={activeTab} open={open} onSelectTab={selectTab} />

        {open && (
          <aside className="relative h-full w-[min(calc(100vw-2.75rem),380px)] flex flex-col min-h-0 bg-white border border-gray-300 border-l-0 rounded-r-none shadow-[-12px_0_32px_rgba(15,23,42,0.16),_0_0_0_1px_rgba(15,23,42,0.06)]">
            {sidebarNotice ? (
              <FloatingNotice
                message={sidebarNotice}
                exiting={sidebarNoticeExiting}
                onDismiss={dismissSidebarNotice}
                tone="success"
                className="absolute top-3 left-3 right-3 z-10 text-xs"
              />
            ) : null}

            <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-200 bg-white flex-shrink-0">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-800 truncate">
                {activeConfig.label}
              </p>
              <p className="text-[11px] text-gray-500 truncate">{activeConfig.subtitle}</p>
            </div>

            <div className="flex items-center gap-1 flex-shrink-0">
              {activeTab === "rovo" && (
                <button
                  type="button"
                  onClick={() => void copyRequest()}
                  className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-brand-red hover:bg-brand-red/10 rounded-md"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {copyHint || "Copy"}
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                title="Collapse sidebar"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3">
            {activeTab === "rovo" ? (
              <RovoPanel
                assignees={assignees}
                employeesLoading={employeesLoading}
                employeesError={employeesError}
                activityStart={activityStart}
                activityEnd={activityEnd}
                onDateChange={(s, e) => {
                  setActivityStart(s);
                  setActivityEnd(e);
                }}
                snapshotIso={snapshotIso}
              />
            ) : activeTab === "assignees" ? (
              <AssigneeEditorPanel
                trackCatalog={trackCatalog}
                onChanged={handleAssigneeChanged}
              />
            ) : (
              <TrackEditorPanel onChanged={handleTracksChanged} />
            )}
          </div>
        </aside>
        )}
      </div>
    </div>
  );
}
