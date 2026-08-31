export interface TrackListItem {
  project_id: number;
  project_key: string;
  project_name: string;
  is_active?: boolean;
}

export interface TrackResponse extends TrackListItem {
  track_id: number;
}

export interface TrackListResponse {
  count: number;
  tracks: TrackResponse[];
}

export interface TrackCreatePayload {
  project_key: string;
  project_name: string;
  is_active?: boolean;
}

export interface TrackUpdatePayload {
  is_active: boolean;
}

export interface TeamTracksResponse {
  team_name: string;
  tracks: TrackListItem[];
}

/** Map API track rows to sidebar / DSR track entries (dynamic from DB). */
export function catalogToImportedTracks(
  catalog: TrackListItem[],
): Array<{
  id: string;
  name: string;
  codes: string[];
  fullName: string;
  projectId: number;
}> {
  return catalog.map((c) => ({
    id: `db-${c.project_id}`,
    name: c.project_name,
    codes: [c.project_key],
    fullName: c.project_name,
    projectId: c.project_id,
  }));
}

/** Whether the track is active in the projects catalog (inactive tracks are not assignable). */
export function isCatalogTrackActive(item: TrackListItem): boolean {
  return item.is_active !== false;
}

export function isProjectTrackInactive(
  catalog: TrackListItem[],
  projectId: number,
): boolean {
  const track = catalog.find((t) => t.project_id === projectId);
  return track?.is_active === false;
}

/** View DSR sidebar: active tracks only; hide LOCO and legacy Pricing (PRC); keep PRICE. */
export function isViewDsrSidebarTrack(item: TrackListItem): boolean {
  if (!isCatalogTrackActive(item)) return false;
  const key = item.project_key.trim().toUpperCase();
  const name = item.project_name.trim().toUpperCase();
  if (key === "PRICE") return true;
  if (key === "LOCO" || key === "PRC") return false;
  if (name === "LOCO" || name === "PRICING") return false;
  if (key === "LOC" && name === "LOCO") return false;
  return true;
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

export async function fetchTeamTracks(teamName = "HEB"): Promise<TeamTracksResponse> {
  const res = await fetch(`/api/teams/${encodeURIComponent(teamName)}/tracks`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<TeamTracksResponse>;
}

export async function fetchTracks(options?: {
  activeOnly?: boolean;
}): Promise<TrackListResponse> {
  const qs = options?.activeOnly ? "?active_only=true" : "";
  const res = await fetch(`/api/tracks${qs}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<TrackListResponse>;
}

export async function createTrack(payload: TrackCreatePayload): Promise<TrackResponse> {
  const res = await fetch("/api/tracks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<TrackResponse>;
}

export async function updateTrack(
  trackId: number,
  payload: TrackUpdatePayload,
): Promise<TrackResponse> {
  const res = await fetch(`/api/tracks/${trackId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<TrackResponse>;
}
