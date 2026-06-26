import { AdminOverviewView } from "@/components/admin-overview";
import { getAdminOverviewServer, getOrgUsageSummaryServer } from "@/lib/api/admin";

export const dynamic = "force-dynamic";

export default async function AdminOverviewPage() {
  let overview: Awaited<ReturnType<typeof getAdminOverviewServer>>["data"] | null = null;
  let orgUsage: Awaited<ReturnType<typeof getOrgUsageSummaryServer>>["data"] | null = null;
  let error: string | null = null;

  try {
    const [overviewResponse, orgResponse] = await Promise.all([
      getAdminOverviewServer(),
      getOrgUsageSummaryServer(),
    ]);
    overview = overviewResponse.data;
    orgUsage = orgResponse.data;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load admin overview";
  }

  return <AdminOverviewView overview={overview} orgUsage={orgUsage} error={error} />;
}
