import type { AuthSessionResponse, AuthUserProfile } from "../api/types";

export interface AuthSession extends AuthSessionResponse {
  signed_in_at: string;
}

const SESSION_STORAGE_KEY = "lidmas.auth.session";
export const AUTH_UPDATED_EVENT = "lidmas:auth-updated";

function readJson<T>(raw: string | null): T | null {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function isSessionExpired(expiresAt: string): boolean {
  const timestamp = new Date(expiresAt).getTime();
  if (!Number.isFinite(timestamp)) {
    return true;
  }
  return Date.now() >= timestamp;
}

export function loadAuthSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }
  const parsed = readJson<AuthSession>(window.localStorage.getItem(SESSION_STORAGE_KEY));
  if (!parsed?.token || !parsed?.token_type || !parsed?.expires_at || !parsed?.user) {
    return null;
  }
  if (isSessionExpired(parsed.expires_at)) {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
  return parsed;
}

export function saveAuthSession(payload: AuthSessionResponse): AuthSession {
  const session: AuthSession = {
    ...payload,
    signed_in_at: new Date().toISOString(),
  };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
    window.dispatchEvent(new Event(AUTH_UPDATED_EVENT));
  }
  return session;
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
  window.dispatchEvent(new Event(AUTH_UPDATED_EVENT));
}

export function sessionUserDisplayName(user: AuthUserProfile | null | undefined): string {
  if (!user) {
    return "Guest";
  }
  const value = user.full_name.trim();
  return value || "Guest";
}
