"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { scheduleDatasetEmbargo } from "@/lib/api/client";

interface EmbargoSchedulerProps {
  datasetId: string;
  onScheduled?: () => void;
}

export function EmbargoScheduler({ datasetId, onScheduled }: EmbargoSchedulerProps) {
  const defaultValue = () => {
    const dt = new Date(Date.now() + 24 * 60 * 60 * 1000);
    dt.setMinutes(0, 0, 0);
    return dt.toISOString().slice(0, 16);
  };
  const [embargoUntil, setEmbargoUntil] = useState(defaultValue);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSchedule() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const iso = new Date(embargoUntil).toISOString();
      await scheduleDatasetEmbargo(datasetId, iso);
      setMessage("Publication scheduled. Dataset will go live at the embargo time.");
      onScheduled?.();
    } catch (scheduleError) {
      setError(scheduleError instanceof Error ? scheduleError.message : "Schedule failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-dashed border-[var(--color-border)] p-3">
      <p className="mb-2 text-sm font-medium">Schedule embargo publication</p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-sm">
          <span className="text-[var(--color-foreground-muted)]">Publish at (local)</span>
          <Input
            type="datetime-local"
            value={embargoUntil}
            onChange={(e) => setEmbargoUntil(e.target.value)}
          />
        </label>
        <Button type="button" variant="secondary" disabled={busy} onClick={() => void handleSchedule()}>
          {busy ? "Scheduling…" : "Schedule"}
        </Button>
      </div>
      {error ? (
        <p className="mt-2 text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="mt-2 text-sm text-[var(--color-foreground-secondary)]">{message}</p> : null}
    </div>
  );
}
