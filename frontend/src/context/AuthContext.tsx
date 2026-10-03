import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import { getRefreshToken } from "../api/tokenStore";

type Status = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: authApi.UserInfo | null;
  status: Status;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, nome?: string, inviteCode?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<authApi.UserInfo | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  // Refresh silenzioso al boot: se c'è un refresh_token salvato, l'utente arriva
  // direttamente alla lista prodotti senza dover rifare login.
  useEffect(() => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      setStatus("unauthenticated");
      return;
    }
    authApi
      .bootstrapSession(refreshToken)
      .then((bootUser) => {
        setUser(bootUser);
        setStatus("authenticated");
      })
      .catch(() => setStatus("unauthenticated"));
  }, []);

  const login = async (email: string, password: string) => {
    const loggedInUser = await authApi.login(email, password);
    setUser(loggedInUser);
    setStatus("authenticated");
  };

  const register = async (email: string, password: string, nome?: string, inviteCode?: string) => {
    const registeredUser = await authApi.register(email, password, nome, inviteCode);
    setUser(registeredUser);
    setStatus("authenticated");
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
    setStatus("unauthenticated");
  };

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve essere usato dentro <AuthProvider>");
  return ctx;
}
