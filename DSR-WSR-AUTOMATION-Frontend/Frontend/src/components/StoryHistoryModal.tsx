import { useEffect, useMemo, useState } from "react";
import { GitCommit, Loader2, X } from "lucide-react";
import {
  apiStoryToRecord,
  fetchStoryHistory,
  type JiraStoryRecord,
} from "@/api/stories";

const TRACKED_FIELDS: { key: keyof JiraStoryRecord; label: string }[] = [
  { key: "status", label: "Status" },
  { key: "assignee", label: "Assignee" },
  { key: "title", label: "Title" },
  { key: "summary", label: "Summary" },
  { key: "story_points", label: "Story points" },
  { key: "sprint_name", label: "Sprint" },
  { key: "date_assigned", label: "Date assigned" },
  { key: "reportee", label: "Reportee" },
  { key: "comment", label: "Comment" },
  { key: "priority", label: "Priority" },
  { key: "issue_type", label: "Issue type" },
];

function formatFieldValue(value: unknown): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function formatSnapshotLabel(snapshotDate: string): string {
  const raw = snapshotDate?.slice(0, 10) || "";
  const d = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(d.getTime())) return raw || "Unknown date";
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatTimestamp(snapshotDate: string): string {
  return `Snapshot ${formatSnapshotLabel(snapshotDate)}`;
}

function computeChanges(
  current: JiraStoryRecord,
  previous: JiraStoryRecord | null,
): string[] {
  if (!previous) {
    return ["Initial snapshot recorded."];
  }

  const changes: string[] = [];
  for (const { key, label } of TRACKED_FIELDS) {
    const cur = formatFieldValue(current[key]);
    const prev = formatFieldValue(previous[key]);
    if (cur !== prev) {
      changes.push(`${label}: ${prev} → ${cur}`);
    }
  }
  return changes.length > 0 ? changes : ["No tracked field changes from previous snapshot."];
}

interface StoryHistoryModalProps {
  jiraKey: string;
  onClose: () => void;
}

export function StoryHistoryModal({ jiraKey, onClose }: StoryHistoryModalProps) {
  const [versions, setVersions] = useState<JiraStoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    void fetchStoryHistory(jiraKey)
      .then((response) => {
        if (cancelled) return;
        setVersions(response.stories.map(apiStoryToRecord));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setVersions([]);
        setError(err instanceof Error ? err.message : "Failed to load history");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jiraKey]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const timeline = useMemo(
    () =>
      versions.map((version, index) => ({
        version,
        changes: computeChanges(version, versions[index + 1] ?? null),
        isLatest: index === 0,
      })),
    [versions],
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[min(90vh,720px)] bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-gray-200 bg-gray-50">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
              Version history
            </p>
            <h2 className="text-lg font-semibold text-gray-900">{jiraKey}</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Newest snapshot first, like commit history on a branch.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-400 hover:bg-white hover:text-gray-600"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex flex-col items-center justify-center py-16 text-gray-500">
              <Loader2 className="w-6 h-6 animate-spin mb-2" />
              <p className="text-sm">Loading version history…</p>
            </div>
          )}

          {!loading && error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && timeline.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-12">No versions found.</p>
          )}

          {!loading && !error && timeline.length > 0 && (
            <ol className="relative border-l border-gray-200 ml-3 space-y-0">
              {timeline.map(({ version, changes, isLatest }, index) => (
                <li key={storyVersionKey(version, index)} className="relative pl-8 pb-8 last:pb-2">
                  <span
                    className={`absolute -left-[7px] top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full ring-4 ring-white ${
                      isLatest ? "bg-brand-red" : "bg-gray-300"
                    }`}
                  />

                  <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
                    <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/80">
                      <div className="flex flex-wrap items-center gap-2">
                        <GitCommit className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <p className="text-sm font-semibold text-gray-900">
                          {formatTimestamp(version.snapshot_date)}
                        </p>
                        {isLatest && (
                          <span className="px-2 py-0.5 rounded-full bg-brand-red/10 text-brand-red text-[10px] font-bold uppercase tracking-wide">
                            Latest
                          </span>
                        )}
                      </div>
                      <p className="mt-2 text-sm text-gray-800 leading-snug">
                        {version.title?.trim() || version.summary || "Untitled"}
                      </p>
                    </div>

                    <div className="px-4 py-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
                      <p>
                        <span className="text-gray-400">Status:</span> {version.status || "—"}
                      </p>
                      <p>
                        <span className="text-gray-400">Assignee:</span> {version.assignee || "—"}
                      </p>
                      <p>
                        <span className="text-gray-400">Sprint:</span> {version.sprint_name || "—"}
                      </p>
                      <p>
                        <span className="text-gray-400">Points:</span>{" "}
                        {version.story_points ?? "—"}
                      </p>
                      {version.comment?.trim() ? (
                        <p className="col-span-2">
                          <span className="text-gray-400">Comment:</span> {version.comment}
                        </p>
                      ) : null}
                    </div>

                    <div className="px-4 py-3 border-t border-gray-100 bg-white">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2">
                        Changes
                      </p>
                      <ul className="space-y-1">
                        {changes.map((change) => (
                          <li key={change} className="text-xs text-gray-700 font-mono leading-relaxed">
                            {change}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

function storyVersionKey(version: JiraStoryRecord, index: number): string {
  return `${version.jira_key}::${version.snapshot_date || index}`;
}

export function StoryHistoryButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title="View version history"
      className="inline-flex items-center justify-center w-7 h-7 rounded-md border border-gray-200 text-gray-500 hover:text-brand-red hover:border-brand-red/30 hover:bg-brand-red/10 disabled:opacity-40 disabled:pointer-events-none"
    >
      <GitCommit className="w-3.5 h-3.5" />
    </button>
  );
}
