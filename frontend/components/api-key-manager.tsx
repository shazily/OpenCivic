"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createApiKeyClient, revokeApiKeyClient } from "@/lib/api/developer-client";

export function ApiKeyManager({
  initialKeys,
}: {
  initialKeys: Array<{
    id: string;
    name: string;
    key_prefix: string;
    scopes: string[];
    revoked_at: string | null;
    created_at: string;
  }>;
}) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  async function handleCreate() {
    setBusy(true);
    setError(null);
    setCreatedKey(null);
    try {
      const response = await createApiKeyClient(name.trim(), ["read"]);
      setCreatedKey(response.data.raw_key);
      setName("");
      router.refresh();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(keyId: string) {
    setBusy(true);
    setError(null);
    try {
      await revokeApiKeyClient(keyId);
      router.refresh();
    } catch (revokeError) {
      setError(revokeError instanceof Error ? revokeError.message : "Revoke failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-[var(--color-border)] p-4">
        <h2 className="mb-3 text-lg font-semibold">Create API key</h2>
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid flex-1 gap-1 text-sm">
            <span>Name</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Production read" />
          </label>
          <Button type="button" disabled={busy || !name.trim()} onClick={() => void handleCreate()}>
            {busy ? "Creating…" : "Create key"}
          </Button>
        </div>
        {createdKey ? (
          <p className="mt-3 rounded-md bg-[var(--color-background-secondary)] p-3 font-mono text-xs">
            Copy now — this key is shown once: <strong>{createdKey}</strong>
          </p>
        ) : null}
        {error ? (
          <p className="mt-2 text-sm text-[var(--color-danger)]" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Your keys</h2>
        {initialKeys.length === 0 ? (
          <p className="text-sm text-[var(--color-foreground-muted)]">No API keys yet.</p>
        ) : (
          <ul className="space-y-2">
            {initialKeys.map((key) => (
              <li
                key={key.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[var(--color-border)] px-4 py-3 text-sm"
              >
                <div>
                  <p className="font-medium">{key.name}</p>
                  <p className="text-[var(--color-foreground-muted)]">
                    {key.key_prefix}… · {key.scopes.join(", ")}
                    {key.revoked_at ? " · revoked" : ""}
                  </p>
                </div>
                {!key.revoked_at ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={busy}
                    onClick={() => void handleRevoke(key.id)}
                  >
                    Revoke
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
