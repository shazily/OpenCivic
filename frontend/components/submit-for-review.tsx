"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { submitDatasetForReview } from "@/lib/api/client";

export function SubmitForReview({ datasetId, status }: { datasetId: string; status: string }) {
  const router = useRouter();
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const canSubmit = ["draft", "changes_requested"].includes(status) && !done;

  if (!canSubmit && !done) {
    return null;
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await submitDatasetForReview(datasetId, notes);
      setDone(true);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <p style={{ color: "var(--color-foreground-secondary)", marginBottom: "1.5rem" }}>
        Submitted for steward review.
      </p>
    );
  }

  return (
    <section
      style={{
        marginBottom: "2rem",
        padding: "1.25rem",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius)",
        background: "var(--color-background-secondary)",
      }}
    >
      <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "0.75rem" }}>
        Submit for review
      </h2>
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder="Notes for the steward (optional)"
        rows={2}
        style={{
          width: "100%",
          marginBottom: "0.75rem",
          padding: "0.5rem",
          borderRadius: "var(--radius)",
          border: "1px solid var(--color-border)",
        }}
      />
      <button type="button" disabled={busy} onClick={submit}>
        {busy ? "Submitting…" : "Submit for review"}
      </button>
      {error ? (
        <p role="alert" style={{ marginTop: "0.75rem", color: "var(--color-destructive, #b91c1c)" }}>
          {error}
        </p>
      ) : null}
    </section>
  );
}
