export interface EmployeeTrackItem {
  employee_id: number;
  employee_name: string;
  team_id: number;
  team_name: string;
  project_id: number;
  track_id: number;
  project_key: string;
  project_name: string;
  is_active: boolean;
}

export interface EmployeeTrackListResponse {
  count: number;
  employees: EmployeeTrackItem[];
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

export async function fetchEmployeesByTrack(
  trackId: number,
  options: { activeOnly?: boolean } = {},
): Promise<EmployeeTrackListResponse> {
  const params = new URLSearchParams();
  if (options.activeOnly) params.set("active_only", "true");
  const qs = params.toString();
  const res = await fetch(
    `/api/employees/track/${trackId}${qs ? `?${qs}` : ""}`,
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<EmployeeTrackListResponse>;
}

export async function fetchEmployeesByTeam(
  teamName: string,
  options: { activeOnly?: boolean } = {},
): Promise<EmployeeTrackListResponse> {
  const params = new URLSearchParams();
  if (options.activeOnly) params.set("active_only", "true");
  const qs = params.toString();
  const res = await fetch(
    `/api/employees/team/${encodeURIComponent(teamName)}${qs ? `?${qs}` : ""}`,
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<EmployeeTrackListResponse>;
}

export interface CreateEmployeePayload {
  employee_name: string;
  team_name: string;
  project_id: number;
  is_active?: boolean;
}

export interface EmployeeDetailResponse {
  employee_id: number;
  employee_name: string;
  team_id: number;
  team_name: string;
  tracks: EmployeeTrackItem[];
}

export interface AssignTrackPayload {
  project_id: number;
  is_active?: boolean;
}

export async function fetchEmployeeById(
  employeeId: number,
): Promise<EmployeeDetailResponse> {
  const res = await fetch(`/api/employees/${employeeId}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<EmployeeDetailResponse>;
}

export async function createEmployee(
  payload: CreateEmployeePayload,
): Promise<EmployeeTrackItem> {
  const res = await fetch("/api/employees", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      employee_name: payload.employee_name,
      team_name: payload.team_name,
      project_id: payload.project_id,
      is_active: payload.is_active ?? true,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<EmployeeTrackItem>;
}

export async function assignTrackToEmployee(
  employeeId: number,
  payload: AssignTrackPayload,
): Promise<EmployeeTrackItem> {
  const res = await fetch(`/api/employees/${employeeId}/tracks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: payload.project_id,
      is_active: payload.is_active ?? true,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<EmployeeTrackItem>;
}

export async function updateEmployeeTrack(
  employeeId: number,
  trackId: number,
  isActive: boolean,
): Promise<EmployeeTrackItem> {
  const res = await fetch(`/api/employees/${employeeId}/tracks/${trackId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_active: isActive }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<EmployeeTrackItem>;
}

export async function removeEmployeeTrack(
  employeeId: number,
  trackId: number,
): Promise<void> {
  const res = await fetch(`/api/employees/${employeeId}/tracks/${trackId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await parseError(res));
}
