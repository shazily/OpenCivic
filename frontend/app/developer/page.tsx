import { DeveloperOverview } from "@/components/developer-overview";
import { getDeveloperSdkServer, listApiKeysServer } from "@/lib/api/developer";

export const dynamic = "force-dynamic";

export default async function DeveloperOverviewPage() {
  const keys = await listApiKeysServer();
  const sdk = await getDeveloperSdkServer();

  return (
    <DeveloperOverview
      keyCount={keys.meta.total_count ?? keys.data.length}
      pythonSnippet={sdk.data.python}
    />
  );
}
