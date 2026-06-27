import { ApiKeyManager } from "@/components/api-key-manager";
import { DeveloperPageHeader } from "@/components/developer-page-header";
import { listApiKeysServer } from "@/lib/api/developer";

export const dynamic = "force-dynamic";

export default async function ApiKeysPage() {
  let keys: Awaited<ReturnType<typeof listApiKeysServer>>["data"] = [];
  let error: string | null = null;

  try {
    const response = await listApiKeysServer();
    keys = response.data;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load API keys";
  }

  return (
    <div className="space-y-4">
      <DeveloperPageHeader
        titleKey="developer.apiKeys.title"
        descriptionKey="developer.apiKeys.description"
        error={error}
      />
      <ApiKeyManager initialKeys={keys} />
    </div>
  );
}
