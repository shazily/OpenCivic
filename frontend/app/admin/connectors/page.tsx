import { AdminConnectorsPanel } from "@/components/admin-connectors-panel";
import { listConnectorsServer } from "@/lib/api/admin";

export const dynamic = "force-dynamic";

export default async function AdminConnectorsPage() {
  let connectors: Awaited<ReturnType<typeof listConnectorsServer>>["data"] = [];
  let error: string | null = null;

  try {
    const response = await listConnectorsServer();
    connectors = response.data;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load connectors";
  }

  return <AdminConnectorsPanel connectors={connectors} error={error} />;
}
