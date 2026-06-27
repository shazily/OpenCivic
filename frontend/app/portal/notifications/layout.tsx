import { PublisherShell } from "@/components/publisher-shell";

export default function PublisherNotificationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <PublisherShell surface="publisher">{children}</PublisherShell>;
}
