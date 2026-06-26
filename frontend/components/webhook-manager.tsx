"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createWebhookClient, deleteWebhookClient, testWebhookClient } from "@/lib/api/developer-client";

export function WebhookManager({
  initialWebhooks,
}: {
  initialWebhooks: Array<{
    id: string;
    url: string;
    events: string[];
    status: string;
    failure_count: number;
  }>;
}) {
  const router = useRouter();
  const [url, setUrl] = useState("https://example.com/hooks/opencivic");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      await createWebhookClient(url.trim(), ["DatasetPublished"]);
      router.refresh();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleTest(webhookId: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await testWebhookClient(webhookId);
      if (result.data.status !== "ok") {
        setError(`Test delivery failed (${result.data.status})`);
      }
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : "Test failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(webhookId: string) {
    setBusy(true);
    setError(null);
    try {
      await deleteWebhookClient(webhookId);
      router.refresh();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-[var(--color-border)] p-4">
        <h2 className="mb-3 text-lg font-semibold">Register webhook</h2>
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid flex-1 gap-1 text-sm">
            <span>Endpoint URL</span>
            <Input value={url} onChange={(e) => setUrl(e.target.value)} />
          </label>
          <Button type="button" disabled={busy || !url.trim()} onClick={() => void handleCreate()}>
            {busy ? "Saving…" : "Add webhook"}
          </Button>
        </div>
        {error ? (
          <p className="mt-2 text-sm text-[var(--color-danger)]" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Active webhooks</h2>
        {initialWebhooks.length === 0 ? (
          <p className="text-sm text-[var(--color-foreground-muted)]">No webhooks configured.</p>
        ) : (
          <ul className="space-y-2">
            {initialWebhooks.map((hook) => (
              <li
                key={hook.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[var(--color-border)] px-4 py-3 text-sm"
              >
                <div>
                  <p className="font-medium break-all">{hook.url}</p>
                  <p className="text-[var(--color-foreground-muted)]">
                    {hook.events.join(", ")} · failures {hook.failure_count}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => void handleTest(hook.id)}
                  >
                    Test
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={busy}
                    onClick={() => void handleDelete(hook.id)}
                  >
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
