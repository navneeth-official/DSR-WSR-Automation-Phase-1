export interface JiraStoryApiResponse {
  jira_key: string;
  project_id: number;
  project_key: string;
  project_name: string;
  sprint_id: number | null;
  sprint_name: string | null;
  sprint_start_date: string | null;
  sprint_end_date: string | null;
  title: string | null;
  summary: string;
  description: string | null;
  issue_type: string | null;
  priority: string | null;
  assignee: string | null;
  reportee: string | null;
  status: string;
  story_points: number | string | null;
  percent_complete: number | string | null;
  date_assigned: string | null;
  updated_date: string | null;
  resolved_date: string | null;
  snapshot_date: string | null;
  comment?: string | null;
}

export interface JiraStoryListResponse {
  count: number;
  stories: JiraStoryApiResponse[];
}

export interface JiraStoryRecord {
  project_key: string;
  project_name: string;
  sprint_name: string;
  sprint_start_date: string;
  sprint_end_date: string;
  jira_key: string;
  title?: string | null;
  summary: string;
  description: string;
  issue_type: string;
  priority: string;
  assignee: string;
  reporter: string;
  status: string;
  story_points: number | null;
  created_date: string;
  updated_date: string;
  resolved_date: string | null;
  snapshot_date: string;
  date_assigned?: string;
  reportee?: string;
  project_id?: number;
  sprint_id?: number | null;
  isDraft?: boolean;
  comment?: string | null;
}

export interface StorySavePayload {
  jira_key: string;
  summary: string;
  track: string;
  sprint?: string | null;
  sprint_start_date?: string | null;
  sprint_end_date?: string | null;
  date_assigned?: string | null;
  status: string;
  story_points?: number | null;
  percent_complete?: number | null;
  assignee?: string | null;
  reportee?: string | null;
  title?: string | null;
  description?: string | null;
  issue_type?: string | null;
  priority?: string | null;
  updated_date?: string | null;
  resolved_date?: string | null;
  snapshot_date?: string | null;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string | { msg?: string }[] };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`;
}

function toNum(v: number | string | null | undefined): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

/** ISO date (YYYY-MM-DD) for today's snapshot upserts. */
export function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function snapshotSortKey(snapshot: string | null | undefined): number {
  if (!snapshot) return 0;
  const t = Date.parse(snapshot.slice(0, 10));
  return Number.isNaN(t) ? 0 : t;
}

/** Composite row identity: jira_key + snapshot_date. */
export function storyRowKey(
  row: Pick<JiraStoryRecord, "jira_key" | "snapshot_date">,
): string {
  const snap = row.snapshot_date?.slice(0, 10) || todayIsoDate();
  return `${row.jira_key}::${snap}`;
}

/**
 * When the API returns multiple snapshots for the same jira_key, keep only the
 * newest snapshot_date (ties broken by updated_date).
 */
export function pickLatestStoriesPerKey<T extends JiraStoryApiResponse>(
  stories: T[],
): T[] {
  const byKey = new Map<string, T>();
  for (const story of stories) {
    const existing = byKey.get(story.jira_key);
    if (!existing) {
      byKey.set(story.jira_key, story);
      continue;
    }
    const curSnap = snapshotSortKey(story.snapshot_date);
    const existSnap = snapshotSortKey(existing.snapshot_date);
    if (curSnap > existSnap) {
      byKey.set(story.jira_key, story);
    } else if (
      curSnap === existSnap &&
      snapshotSortKey(story.updated_date) >= snapshotSortKey(existing.updated_date)
    ) {
      byKey.set(story.jira_key, story);
    }
  }
  return [...byKey.values()];
}

function normalizeListResponse(
  response: JiraStoryListResponse,
): JiraStoryListResponse {
  const stories = pickLatestStoriesPerKey(response.stories);
  return { count: stories.length, stories };
}

/** Map API stories to records, keeping only the latest snapshot per jira_key. */
export function storiesToLatestRecords(
  stories: JiraStoryApiResponse[],
): JiraStoryRecord[] {
  return pickLatestStoriesPerKey(stories).map(apiStoryToRecord);
}

/** Collapse in-memory rows to the latest snapshot per jira_key (drafts preserved). */
export function dedupeLatestRecords(rows: JiraStoryRecord[]): JiraStoryRecord[] {
  const drafts = rows.filter((r) => r.isDraft);
  const latest = new Map<string, JiraStoryRecord>();
  for (const row of rows) {
    if (row.isDraft) continue;
    const existing = latest.get(row.jira_key);
    if (!existing) {
      latest.set(row.jira_key, row);
      continue;
    }
    const curSnap = snapshotSortKey(row.snapshot_date);
    const existSnap = snapshotSortKey(existing.snapshot_date);
    if (curSnap > existSnap) {
      latest.set(row.jira_key, row);
    } else if (
      curSnap === existSnap &&
      snapshotSortKey(row.updated_date) >= snapshotSortKey(existing.updated_date)
    ) {
      latest.set(row.jira_key, row);
    }
  }
  return [...latest.values(), ...drafts];
}

export function apiStoryToRecord(s: JiraStoryApiResponse): JiraStoryRecord {
  return {
    jira_key: s.jira_key,
    project_id: s.project_id,
    project_key: s.project_key,
    project_name: s.project_name,
    sprint_id: s.sprint_id,
    sprint_name: s.sprint_name ?? "",
    sprint_start_date: s.sprint_start_date ?? "",
    sprint_end_date: s.sprint_end_date ?? "",
    title: s.title,
    summary: s.summary,
    description: s.description ?? "",
    issue_type: s.issue_type ?? "",
    priority: s.priority ?? "",
    assignee: s.assignee ?? "",
    reporter: s.reportee ?? "",
    reportee: s.reportee ?? undefined,
    status: s.status,
    story_points: toNum(s.story_points),
    created_date: s.date_assigned ?? "",
    date_assigned: s.date_assigned ?? "",
    updated_date: s.updated_date ?? "",
    resolved_date: s.resolved_date ?? null,
    snapshot_date: s.snapshot_date ?? "",
    comment: s.comment ?? null,
  };
}

export function recordToSavePayload(
  row: JiraStoryRecord,
  trackCode?: string,
): StorySavePayload {
  const pct = toNum(
    row.status === "Done" ? 100 : row.status === "In Progress" ? 50 : 0,
  );
  return {
    jira_key: row.jira_key,
    summary: row.summary,
    track: trackCode ?? row.project_key,
    sprint: row.sprint_name || null,
    sprint_start_date: row.sprint_start_date || null,
    sprint_end_date: row.sprint_end_date || null,
    date_assigned: row.date_assigned || row.created_date || null,
    status: row.status,
    story_points: row.story_points,
    percent_complete: pct,
    assignee: row.assignee || null,
    reportee: row.reportee ?? row.reporter ?? null,
    description: row.description || null,
    issue_type: row.issue_type || null,
    priority: row.priority || null,
    updated_date: row.updated_date || null,
    resolved_date: row.resolved_date,
    snapshot_date: (row.snapshot_date || todayIsoDate()).slice(0, 10),
    ...(row.title ? { title: row.title } : {}),
  };
}

async function parseStoryList(
  res: Response,
  options: { latestOnly?: boolean } = {},
): Promise<JiraStoryListResponse> {
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as JiraStoryListResponse;
  if (options.latestOnly === false) {
    return { count: data.stories.length, stories: data.stories };
  }
  return normalizeListResponse(data);
}

function allVersionsQuery(options?: { latestOnly?: boolean }): string {
  return options?.latestOnly === false ? "?all_versions=true" : "";
}

/** Map API stories to records without collapsing versions. */
export function storiesToRecords(
  stories: JiraStoryApiResponse[],
): JiraStoryRecord[] {
  return stories.map(apiStoryToRecord);
}

export async function fetchAllStories(
  options: { latestOnly?: boolean } = { latestOnly: true },
): Promise<JiraStoryListResponse> {
  const res = await fetch(`/api/stories${allVersionsQuery(options)}`);
  return parseStoryList(res, options);
}

export async function fetchStoriesByTrack(
  trackId: number,
  options: { latestOnly?: boolean } = { latestOnly: true },
): Promise<JiraStoryListResponse> {
  const res = await fetch(
    `/api/stories/track/${trackId}${allVersionsQuery(options)}`,
  );
  return parseStoryList(res, options);
}

/** View DSR: latest stories in sprints active on the given date (server-sorted). */
export async function fetchDsrStoriesByTrack(
  trackId: number,
  dsrDate: string,
): Promise<JiraStoryListResponse> {
  const snap = dsrDate.slice(0, 10);
  const res = await fetch(
    `/api/stories/track/${trackId}/dsr?dsr_date=${encodeURIComponent(snap)}`,
  );
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as JiraStoryListResponse;
  return { count: data.stories.length, stories: data.stories };
}

export async function fetchStoriesByAssignee(
  assignee: string,
  options: { latestOnly?: boolean } = { latestOnly: true },
): Promise<JiraStoryListResponse> {
  const res = await fetch(
    `/api/stories/assignee/${encodeURIComponent(assignee)}${allVersionsQuery(options)}`,
  );
  return parseStoryList(res, options);
}

export async function fetchStoriesBySprint(
  sprintId: number,
  options: { latestOnly?: boolean } = { latestOnly: true },
): Promise<JiraStoryListResponse> {
  const res = await fetch(
    `/api/stories/sprint/${sprintId}${allVersionsQuery(options)}`,
  );
  return parseStoryList(res, options);
}

export async function fetchStoryHistory(jiraKey: string): Promise<JiraStoryListResponse> {
  const res = await fetch(`/api/stories/${encodeURIComponent(jiraKey)}/history`);
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as JiraStoryListResponse;
  return { count: data.stories.length, stories: data.stories };
}

export async function addStoryComment(
  jiraKey: string,
  comment: string,
): Promise<JiraStoryApiResponse> {
  const res = await fetch(`/api/stories/${encodeURIComponent(jiraKey)}/comment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comment }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<JiraStoryApiResponse>;
}

export async function createStory(payload: StorySavePayload): Promise<JiraStoryApiResponse> {
  const res = await fetch("/api/stories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<JiraStoryApiResponse>;
}

export async function updateStory(payload: StorySavePayload): Promise<JiraStoryApiResponse> {
  const res = await fetch("/api/stories", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<JiraStoryApiResponse>;
}

export interface TitleSuggestionsResponse {
  jira_key: string;
  snapshot_date: string | null;
  title: string | null;
  suggestions: string[];
}

export async function regenerateStoryTitle(
  jiraKey: string,
  snapshotDate?: string | null,
): Promise<TitleSuggestionsResponse> {
  const snap = snapshotDate?.slice(0, 10);
  const qs = snap ? `?snapshot_date=${encodeURIComponent(snap)}` : "";
  const res = await fetch(
    `/api/stories/${encodeURIComponent(jiraKey)}/regenerate-title${qs}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<TitleSuggestionsResponse>;
}

/** Persist intake rows to the API; titles are generated server-side on create. */
export async function importStories(
  payload: JiraStoryRecord[] | Record<string, unknown>,
): Promise<{ imported: number; keys: string[]; stories: JiraStoryApiResponse[] }> {
  const rows = Array.isArray(payload)
    ? payload
    : (payload as { tickets?: JiraStoryRecord[] }).tickets ?? [];
  const keys: string[] = [];
  const stories: JiraStoryApiResponse[] = [];
  for (const row of rows) {
    const saved = await createStory(recordToSavePayload(row));
    keys.push(saved.jira_key);
    stories.push(saved);
  }
  return { imported: keys.length, keys, stories };
}
