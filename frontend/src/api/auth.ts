import { apiJson } from "./client";
import { setAccessToken, setRefreshToken } from "./tokenStore";

export interface UserInfo {
  id: string;
  email: string;
  nome: string | null;
  household_id: string;
  household_invite_code: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserInfo;
}

function persistSession(data: TokenResponse): UserInfo {
  setAccessToken(data.access_token);
  setRefreshToken(data.refresh_token);
  return data.user;
}

export async function login(email: string, password: string): Promise<UserInfo> {
  const data = await apiJson<TokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });
  return persistSession(data);
}

export async function register(
  email: string,
  password: string,
  nome?: string,
  inviteCode?: string,
): Promise<UserInfo> {
  const data = await apiJson<TokenResponse>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      nome: nome || undefined,
      invite_code: inviteCode || undefined,
    }),
    skipAuth: true,
  });
  return persistSession(data);
}

/** Chiamata una volta all'avvio dell'app per il refresh silenzioso: nessun login
 * ripetuto se esiste già un refresh_token valido salvato dalla sessione precedente. */
export async function bootstrapSession(refreshToken: string): Promise<UserInfo> {
  const data = await apiJson<TokenResponse>("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    skipAuth: true,
  });
  return persistSession(data);
}

export async function logout(): Promise<void> {
  const refreshToken = localStorage.getItem("scadenzario_refresh_token");
  setAccessToken(null);
  setRefreshToken(null);
  if (refreshToken) {
    await apiJson("/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      skipAuth: true,
    }).catch(() => {
      // logout lato client comunque riuscito anche se la revoca server-side fallisce
    });
  }
}
