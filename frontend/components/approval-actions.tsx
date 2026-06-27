"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { approveSubmission } from "@/lib/api/client";

export function ApprovalActions({ submissionId }: { submissionId: string }) {
  const router = useRouter();
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act() {
    setBusy(true);
    setError(null);
    try {
      await approveSubmission(submissionId, notes);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-3">
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder="Senior approver notes"
        rows={2}
        className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
      />
      <Button type="button" disabled={busy} onClick={() => void act()}>
        Publish (senior approval)
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-[var(--color-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}
