"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import {
  clearSession,
  getAccessToken,
  getStaffRole,
  setAccessToken,
  setSession,
  type StaffRole,
} from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";
const REFRESH_INTERVAL_MS = 12 * 60 * 1000;

interface AuthContextValue {
  token: string | null;
  role: StaffRole | null;
  isLoaded: boolean;
  signOut: () => void;
  refresh: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function silentRefresh(): Promise<string | null> {
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      return null;
    }
    const body = (await response.json()) as { data: { access_token: string } };
    return body.data.access_token ?? null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<StaffRole | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  const refresh = () => {
    setToken(getAccessToken());
    setRole(getStaffRole());
  };

  useEffect(() => {
    void (async () => {
      if (!getAccessToken()) {
        const refreshed = await silentRefresh();
        if (refreshed) {
          const existingRole = getStaffRole();
          if (existingRole) {
            setAccessToken(refreshed);
          }
        }
      }
      refresh();
      setIsLoaded(true);
    })();
  }, []);

  useEffect(() => {
    const currentToken = getAccessToken();
    const currentRole = getStaffRole();
    if (!currentToken && !currentRole) {
      return;
    }
    const interval = window.setInterval(() => {
      void (async () => {
        const refreshed = await silentRefresh();
        if (!refreshed) {
          return;
        }
        const role = getStaffRole();
        if (role) {
          setSession(refreshed, role);
          setToken(refreshed);
        } else {
          setAccessToken(refreshed);
          setToken(refreshed);
        }
      })();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [token, role]);

  const value = useMemo(
    () => ({
      token,
      role,
      isLoaded,
      signOut: () => {
        clearSession();
        refresh();
      },
      refresh,
    }),
    [token, role, isLoaded],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
