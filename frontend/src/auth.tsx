import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "./api";

interface AuthState {
  ready: boolean;
  authed: boolean;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState>(null as unknown as AuthState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    api
      .get<{ authenticated: boolean }>("/api/auth/me")
      .then((r) => setAuthed(r.authenticated))
      .catch(() => setAuthed(false))
      .finally(() => setReady(true));
  }, []);

  const login = async (password: string) => {
    await api.post("/api/auth/login", { password });
    setAuthed(true);
  };
  const logout = async () => {
    await api.post("/api/auth/logout");
    setAuthed(false);
  };

  return <Ctx.Provider value={{ ready, authed, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
