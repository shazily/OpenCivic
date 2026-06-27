import { PublisherShell } from "@/components/publisher-shell";

export default function StewardReviewLayout({ children }: { children: React.ReactNode }) {
  return <PublisherShell surface="steward">{children}</PublisherShell>;
}
