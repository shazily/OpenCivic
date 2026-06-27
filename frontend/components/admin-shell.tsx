"use client";

import { AppShell } from "@/components/layout/app-shell";

export function AdminShell({ children }: { children: React.ReactNode }) {
  return <AppShell surface="admin">{children}</AppShell>;
}
