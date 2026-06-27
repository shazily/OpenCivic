import { PublisherShell } from "@/components/publisher-shell";

export default function PublisherDashboardLayout({ children }: { children: React.ReactNode }) {
  return <PublisherShell surface="publisher">{children}</PublisherShell>;
}
