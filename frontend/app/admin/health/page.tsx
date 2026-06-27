import { AdminHealthPanel } from "@/components/admin-health-panel";
import { getDeepHealthServer } from "@/lib/api/admin";

export const dynamic = "force-dynamic";

export default async function AdminHealthPage() {
  let health: Awaited<ReturnType<typeof getDeepHealthServer>>["data"] | null = null;
  let error: string | null = null;

  try {
    const response = await getDeepHealthServer();
    health = response.data;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load deep health";
  }

  return <AdminHealthPanel health={health} error={error} />;
}
