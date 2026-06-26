"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { CommandPalette } from "@/components/command-palette";
import { I18nProvider } from "@/components/i18n-provider";
import { TenantBrandingProvider } from "@/components/tenant-branding-provider";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60 * 1000, retry: 1 },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <TenantBrandingProvider>
          <AuthProvider>
            {children}
            <CommandPalette />
          </AuthProvider>
        </TenantBrandingProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
