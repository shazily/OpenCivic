"use client";

import { AppShell } from "@/components/layout/app-shell";

export function DeveloperShell({ children }: { children: React.ReactNode }) {
  return <AppShell surface="developer">{children}</AppShell>;
}
