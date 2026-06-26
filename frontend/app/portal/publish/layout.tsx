import { PublisherShell } from "@/components/publisher-shell";

export default function PublisherPublishLayout({ children }: { children: React.ReactNode }) {
  return <PublisherShell surface="publisher">{children}</PublisherShell>;
}
