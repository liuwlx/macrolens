"use client";

import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, displayName: string, password: string): Promise<void>;
  logout(): Promise<void>;
  refresh(): Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const next = await apiFetch<User>("/auth/me");
      setUser(next);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) {
        console.error(error);
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async login(email, password) {
        const result = await apiFetch<{ user: User }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        setUser(result.user);
      },
      async register(email, displayName, password) {
        const result = await apiFetch<{ user: User }>("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, display_name: displayName, password }),
        });
        setUser(result.user);
      },
      async logout() {
        await apiFetch<void>("/auth/logout", { method: "POST" });
        setUser(null);
      },
      refresh,
    }),
    [user, loading, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
