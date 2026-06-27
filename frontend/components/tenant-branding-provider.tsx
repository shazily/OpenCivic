"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8080/api/v1";

const TOKEN_MAP: Record<string, string> = {
  primary_color: "--color-primary",
  primary_hover_color: "--color-primary-hover",
  accent_color: "--color-accent",
};

interface BrandingState {
  displayName: string;
  logoUrl: string | null;
}

const BrandingContext = createContext<BrandingState>({
  displayName: "OpenCivic",
  logoUrl: null,
});

export function useTenantBranding(): BrandingState {
  return useContext(BrandingContext);
}

interface BrandingResponse {
  data: {
    display_name?: string;
    branding: Record<string, string>;
  };
}

/** Fetch tenant branding tokens and inject CSS custom properties on :root. */
export function TenantBrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<BrandingState>({
    displayName: "OpenCivic",
    logoUrl: null,
  });

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/portal/branding`, { cache: "no-store" });
        if (!response.ok) {
          return;
        }
        const body = (await response.json()) as BrandingResponse;
        const root = document.documentElement;
        for (const [key, cssVar] of Object.entries(TOKEN_MAP)) {
          const value = body.data.branding[key];
          if (value) {
            root.style.setProperty(cssVar, value);
          }
        }
        setBranding({
          displayName: body.data.display_name ?? "OpenCivic",
          logoUrl: body.data.branding.logo_url ?? null,
        });
      } catch {
        /* branding is optional — defaults from globals.css apply */
      }
    })();
  }, []);

  const value = useMemo(() => branding, [branding]);

  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>;
}
