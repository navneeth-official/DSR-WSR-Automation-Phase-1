export interface AuthUser {
  user_id: number;
  username: string;
  team_id: number;
  team_name: string;
  is_pmo: boolean;
}

export interface TeamOption {
  team_id: number;
  team_name: string;
}

export interface TeamListResponse {
  count: number;
  teams: TeamOption[];
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string | { msg?: string }[] };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) {
      return data.detail[0].msg ?? `Request failed (${res.status})`;
    }
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`;
}

export async function fetchSignupTeams(): Promise<TeamListResponse> {
  const res = await fetch("/api/auth/teams");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<TeamListResponse>;
}

export async function signupUser(payload: {
  username: string;
  password: string;
  team_name: string;
}): Promise<AuthUser> {
  const res = await fetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<AuthUser>;
}

export async function loginUser(payload: {
  username: string;
  password: string;
}): Promise<AuthUser> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<AuthUser>;
}
