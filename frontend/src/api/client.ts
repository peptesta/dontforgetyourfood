import { getAccessToken, getRefreshToken, setAccessToken, setRefreshToken } from "./tokenStore";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

let refreshPromise: Promise<string | null> | null = null;

async function doRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) {
    setAccessToken(null);
    setRefreshToken(null);
    return null;
  }
  const data = await res.json();
  setAccessToken(data.access_token);
  setRefreshToken(data.refresh_token);
  return data.access_token as string;
}

/** Rifresca la sessione silenziosamente. Deduplica chiamate concorrenti. */
export function refreshSession(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

interface ApiRequestInit extends RequestInit {
  /** true per le chiamate di auth stesse (login/register/refresh): niente Bearer, niente retry su 401. */
  skipAuth?: boolean;
}

export async function apiFetch(path: string, options: ApiRequestInit = {}): Promise<Response> {
  const { skipAuth, headers, ...rest } = options;

  const doRequest = async (): Promise<Response> => {
    const finalHeaders = new Headers(headers);
    if (!skipAuth) {
      const token = getAccessToken();
      if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
    }
    return fetch(`${API_BASE}${path}`, { ...rest, headers: finalHeaders });
  };

  let response = await doRequest();
  if (response.status === 401 && !skipAuth) {
    const newToken = await refreshSession();
    if (newToken) {
      response = await doRequest();
    }
  }
  return response;
}

export async function apiJson<T>(path: string, options: ApiRequestInit = {}): Promise<T> {
  const response = await apiFetch(path, options);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}) as Record<string, unknown>);
    const message = typeof detail.detail === "string" ? detail.detail : `Errore ${response.status}`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
