"use client";

import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { chatWithDatasetClient } from "@/lib/api/client";

interface DatasetChatProps {
  datasetId: string;
  published: boolean;
  hasData: boolean;
}

function confidenceVariant(score: number): "success" | "warning" | "danger" {
  if (score >= 0.8) {
    return "success";
  }
  if (score >= 0.5) {
    return "warning";
  }
  return "danger";
}

export function DatasetChat({ datasetId, published, hasData }: DatasetChatProps) {
  const { t } = useTranslation();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [aiAssisted, setAiAssisted] = useState(false);
  const [citation, setCitation] = useState<{
    query?: string | null;
    columns?: string[];
    rows?: unknown[];
  } | null>(null);
  const [watermark, setWatermark] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!published || !hasData) {
    return null;
  }

  async function handleAsk() {
    const trimmed = question.trim();
    if (!trimmed) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await chatWithDatasetClient(datasetId, trimmed);
      const data = response.data;
      setAnswer(data.answer);
      setConfidence(typeof data.confidence === "number" ? data.confidence : null);
      setAiAssisted(Boolean(data.ai_assisted));
      setCitation(data.citation ?? null);
      setWatermark(data.watermark ?? null);
    } catch (askError) {
      setAnswer(null);
      setCitation(null);
      setConfidence(null);
      setAiAssisted(false);
      setError(askError instanceof Error ? askError.message : t("chat.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mb-8 rounded-lg border border-[var(--color-border)] p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <MessageSquare className="h-5 w-5 text-[var(--color-foreground-muted)]" />
        <h2 className="text-lg font-semibold">{t("chat.title")}</h2>
        {aiAssisted ? <Badge variant="info">{t("chat.aiBadge")}</Badge> : null}
      </div>
      <p className="mb-4 text-sm text-[var(--color-foreground-secondary)]">
        {t("chat.description")}
      </p>
      <div className="flex flex-wrap gap-2">
        <Input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={t("chat.placeholder")}
          className="max-w-xl flex-1"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void handleAsk();
            }
          }}
        />
        <Button type="button" disabled={busy} onClick={() => void handleAsk()}>
          {busy ? t("chat.thinking") : t("chat.ask")}
        </Button>
      </div>
      {error ? (
        <p className="mt-3 text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      {answer ? (
        <div className="mt-4 rounded-md bg-[var(--color-background-secondary)] p-3 text-sm">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            {confidence != null ? (
              <Badge variant={confidenceVariant(confidence)}>
                {t("chat.confidence", { percent: Math.round(confidence * 100) })}
              </Badge>
            ) : null}
            {confidence != null && confidence < 0.5 ? (
              <span className="text-xs text-[var(--color-foreground-muted)]">
                {t("chat.lowConfidence")}
              </span>
            ) : null}
          </div>
          <p>{answer}</p>
          {watermark ? <p className="ai-assisted">{watermark}</p> : null}
          {citation?.columns && citation.columns.length > 0 ? (
            <p className="mt-2 text-xs text-[var(--color-foreground-muted)]">
              {t("chat.citationColumns")}: {citation.columns.join(", ")}
            </p>
          ) : null}
          {citation?.query ? (
            <pre className="mt-2 overflow-x-auto rounded border border-[var(--color-border)] bg-[var(--color-background)] p-2 text-xs">
              {citation.query}
            </pre>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
