import { StewardReviewCard } from "@/components/steward-review-card";
import { StewardReviewIntro } from "@/components/steward-review-intro";
import { getGovernanceSummaryServer, listWorkflowQueueServer } from "@/lib/api/server";

export const dynamic = "force-dynamic";

export default async function ReviewQueuePage() {
  let items: Awaited<ReturnType<typeof listWorkflowQueueServer>>["data"] = [];
  let summary: Awaited<ReturnType<typeof getGovernanceSummaryServer>>["data"] | null = null;
  let loadError: string | null = null;

  try {
    const [queueResponse, summaryResponse] = await Promise.all([
      listWorkflowQueueServer(),
      getGovernanceSummaryServer(),
    ]);
    items = queueResponse.data;
    summary = summaryResponse.data;
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Failed to load review queue";
  }

  return (
    <>
        <StewardReviewIntro summary={summary} loadError={loadError} empty={!loadError && items.length === 0} />

        <div className="grid gap-4">
          {items.map((item) => (
            <StewardReviewCard key={item.id} submission={item} />
          ))}
        </div>
    </>
  );
}
