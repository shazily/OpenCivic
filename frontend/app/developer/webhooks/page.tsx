import { WebhookManager } from "@/components/webhook-manager";
import { listWebhooksServer } from "@/lib/api/developer";

export const dynamic = "force-dynamic";

export default async function WebhooksPage() {
  let webhooks: Awaited<ReturnType<typeof listWebhooksServer>>["data"] = [];
  let error: string | null = null;

  try {
    const response = await listWebhooksServer();
    webhooks = response.data;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load webhooks";
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">Webhooks</h1>
      <p className="text-sm text-[var(--color-foreground-secondary)]">
        Receive HTTP callbacks when datasets are published or change workflow state.
      </p>
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <WebhookManager initialWebhooks={webhooks} />
    </div>
  );
}
