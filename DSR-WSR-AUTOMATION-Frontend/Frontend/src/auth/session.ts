/** Idle session ends after this many ms without user activity. */
export const INACTIVITY_TIMEOUT_MS = 5 * 60 * 1000;

const LEGACY_STORAGE_KEY = "dsr_wsr_auth_user";

/** Clear any older persistent login so refresh always starts signed out. */
export function clearLegacyAuthStorage(): void {
  try {
    localStorage.removeItem(LEGACY_STORAGE_KEY);
    sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
