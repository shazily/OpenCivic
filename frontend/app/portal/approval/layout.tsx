import { PublisherShell } from "@/components/publisher-shell";

export default function StewardApprovalLayout({ children }: { children: React.ReactNode }) {
  return <PublisherShell surface="steward">{children}</PublisherShell>;
}
