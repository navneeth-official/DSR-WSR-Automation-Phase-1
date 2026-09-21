/**
 * Authorized users for the HEB Status Tracker UI.
 * Replace / extend this list (or move to backend auth) when integrating SSO.
 */
export type AuthUser = {
  username: string;
  /** Plaintext for local gate only — not for production SSO. */
  password: string;
  department?: string;
};

const AUTHORIZED_USERS: AuthUser[] = [
  { username: "hebautomate", password: "hebautomate" },
];

export function validateCredentials(
  username: string,
  password: string,
): boolean {
  const u = username.trim().toLowerCase();
  const p = password;
  return AUTHORIZED_USERS.some(
    (user) => user.username.toLowerCase() === u && user.password === p,
  );
}

export function isUsernameTaken(username: string): boolean {
  const u = username.trim().toLowerCase();
  return AUTHORIZED_USERS.some((user) => user.username.toLowerCase() === u);
}

export type RegisterUserResult =
  | { ok: true }
  | { ok: false; error: string };

export function registerUser(input: {
  username: string;
  password: string;
  department: string;
}): RegisterUserResult {
  const username = input.username.trim();
  if (!username) {
    return { ok: false, error: "Please enter a username." };
  }
  if (isUsernameTaken(username)) {
    return { ok: false, error: "That username is already taken." };
  }
  if (input.password.length < 6) {
    return { ok: false, error: "Password must be at least 6 characters long." };
  }

  AUTHORIZED_USERS.push({
    username,
    password: input.password,
    department: input.department,
  });
  return { ok: true };
}
