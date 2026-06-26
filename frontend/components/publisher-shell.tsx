"use client";

import { AppShell } from "@/components/layout/app-shell";
import type { StaffSurface } from "@/lib/navigation/surfaces";

interface PublisherShellProps {
  children: React.ReactNode;
  surface?: Extract<StaffSurface, "publisher" | "steward">;
}

export function PublisherShell({ children, surface = "publisher" }: PublisherShellProps) {
  return <AppShell surface={surface}>{children}</AppShell>;
}
