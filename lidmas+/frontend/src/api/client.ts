import { clearAuthSession, loadAuthSession } from "../auth/session";

const DEFAULT_BASE = "http://127.0.0.1:8080/api/v1";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE;

export interface ApiErrorPayload {
  error?: string;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const session = loadAuthSession();
  const headers = new Headers(init?.headers ?? undefined);
  headers.set("content-type", "application/json");
  let sentAuthHeader = false;
  if (session?.token && session?.token_type && !headers.has("authorization")) {
    headers.set("authorization", `${session.token_type} ${session.token}`);
    sentAuthHeader = true;
  } else if (headers.has("authorization")) {
    sentAuthHeader = true;
  }
  const response = await fetch(url, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      if (payload.error) {
        message = payload.error;
      }
    } catch {
      // keep default message
    }
    if (response.status === 401 && sentAuthHeader) {
      clearAuthSession();
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}
