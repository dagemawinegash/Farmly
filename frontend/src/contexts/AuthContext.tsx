"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type AuthContextValue = {
  accessToken: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  setToken: (token: string) => void;
  clearToken: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const [accessToken, setAccessToken] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("farmly_access_token");
  });
  const isHydrated = typeof window !== "undefined";

  const value = useMemo(
    () => ({
      accessToken,
      isAuthenticated: Boolean(accessToken),
      isHydrated,
      setToken: (token: string) => {
        localStorage.setItem("farmly_access_token", token);
        setAccessToken(token);
      },
      clearToken: () => {
        localStorage.removeItem("farmly_access_token");
        setAccessToken(null);
      },
    }),
    [accessToken, isHydrated]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
