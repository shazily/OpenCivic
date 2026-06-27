import { AdminJobsPanel } from "@/components/admin-jobs-panel";
import { getJobsSummaryServer } from "@/lib/api/admin";

export const dynamic = "force-dynamic";

const flowerUrl =
  process.env.NEXT_PUBLIC_FLOWER_URL || "http://127.0.0.1:5555";

export default async function AdminJobsPage() {
  let summary: Awaited<ReturnType<typeof getJobsSummaryServer>>["data"] | null = null;
  let error: string | null = null;

  try {
    const response = await getJobsSummaryServer();
    summary = response.data;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load jobs summary";
  }

  return <AdminJobsPanel flowerUrl={flowerUrl} summary={summary} error={error} />;
}
