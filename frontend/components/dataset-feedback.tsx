"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { submitFeedbackClient } from "@/lib/api/client";

interface DatasetFeedbackProps {
  datasetId: string;
  published: boolean;
}

export function DatasetFeedback({ datasetId, published }: DatasetFeedbackProps) {
  const { t } = useTranslation();
  const [rating, setRating] = useState(5);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!published) {
    return null;
  }

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await submitFeedbackClient({
        dataset_id: datasetId,
        type: "rating",
        rating,
        content: content.trim() || undefined,
      });
      setMessage(t("feedback.thankYou"));
      setContent("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : t("feedback.submitFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mb-8 rounded-lg border border-[var(--color-border)] p-4">
      <h2 className="mb-3 text-lg font-semibold">{t("feedback.title")}</h2>
      <div className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm">
          <span>{t("feedback.ratingLabel")}</span>
          <select
            value={rating}
            onChange={(e) => setRating(Number(e.target.value))}
            className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
          >
            {[5, 4, 3, 2, 1].map((value) => (
              <option key={value} value={value}>
                {t("feedback.stars", { count: value })}
              </option>
            ))}
          </select>
        </label>
        <label className="grid min-w-[200px] flex-1 gap-1 text-sm">
          <span>{t("feedback.commentLabel")}</span>
          <input
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
            placeholder={t("feedback.commentPlaceholder")}
          />
        </label>
        <Button type="button" disabled={busy} onClick={() => void handleSubmit()}>
          {busy ? t("feedback.sending") : t("feedback.submit")}
        </Button>
      </div>
      {error ? (
        <p className="mt-2 text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="mt-2 text-sm text-[var(--color-foreground-secondary)]">{message}</p> : null}
    </section>
  );
}
