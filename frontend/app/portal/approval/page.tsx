import { ApprovalQueuePanel } from "@/components/approval-queue-panel";
import { listApprovalQueueServer } from "@/lib/api/server";

export const dynamic = "force-dynamic";

export default async function ApprovalQueuePage() {
  let items: Awaited<ReturnType<typeof listApprovalQueueServer>>["data"] = [];
  let loadError: string | null = null;

  try {
    const response = await listApprovalQueueServer();
    items = response.data;
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Failed to load approval queue";
  }

  return <ApprovalQueuePanel items={items} loadError={loadError} />;
}
