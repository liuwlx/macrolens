"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

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
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const currentUser = useRef<User | null>(null);

  const exposeUser = useCallback((nextUser: User | null) => {
    const previousUser = currentUser.current;
    const identityChanged = previousUser?.id !== nextUser?.id || previousUser?.role !== nextUser?.role;
    if (identityChanged) queryClient.clear();
    currentUser.current = nextUser;
    setUser(nextUser);
  }, [queryClient]);

  const refresh = useCallback(async () => {
    try {
      const next = await apiFetch<User>("/auth/me");
      exposeUser(next);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) {
        console.error(error);
      }
      exposeUser(null);
    } finally {
      setLoading(false);
    }
  }, [exposeUser]);

  useEffect(() => {
    // Initial session discovery is an external API synchronization that must update auth state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
        exposeUser(result.user);
      },
      async register(email, displayName, password) {
        const result = await apiFetch<{ user: User }>("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, display_name: displayName, password }),
        });
        exposeUser(result.user);
      },
      async logout() {
        await apiFetch<void>("/auth/logout", { method: "POST" });
        exposeUser(null);
      },
      refresh,
    }),
    [user, loading, refresh, exposeUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
