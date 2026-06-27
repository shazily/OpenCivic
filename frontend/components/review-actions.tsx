"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { reviewSubmission } from "@/lib/api/client";

export function ReviewActions({ submissionId }: { submissionId: string }) {
  const router = useRouter();
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(action: "approve" | "reject" | "request_changes") {
    setBusy(true);
    setError(null);
    try {
      await reviewSubmission(submissionId, action, notes);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: "0.75rem" }}>
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder="Review notes"
        rows={2}
        style={{
          padding: "0.5rem",
          borderRadius: "var(--radius)",
          border: "1px solid var(--color-border)",
        }}
      />
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        <button type="button" disabled={busy} onClick={() => act("approve")}>
          Approve
        </button>
        <button type="button" disabled={busy} onClick={() => act("request_changes")}>
          Request changes
        </button>
        <button type="button" disabled={busy} onClick={() => act("reject")}>
          Reject
        </button>
      </div>
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
