"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface DatasetEmbedPanelProps {
  datasetId: string;
  title: string;
}

function portalOrigin(): string {
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  return process.env.NEXT_PUBLIC_PORTAL_URL ?? "http://127.0.0.1:3100";
}

export function DatasetEmbedPanel({ datasetId, title }: DatasetEmbedPanelProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState<"iframe" | "api" | null>(null);

  const origin = useMemo(() => portalOrigin(), []);
  const pageUrl = `${origin}/portal/datasets/${datasetId}`;
  const apiUrl = `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1"}/datasets/${datasetId}/data`;
  const iframeSnippet = `<iframe src="${pageUrl}" title="${title.replace(/"/g, "&quot;")}" width="100%" height="480" loading="lazy" style="border:0;border-radius:8px"></iframe>`;
  const apiSnippet = `curl "${apiUrl}?page_size=100"`;

  const onCopy = async (kind: "iframe" | "api", text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(null);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{t("dataset.embedTitle")}</CardTitle>
        <p className="text-sm text-[var(--color-foreground-secondary)]">
          {t("dataset.embedDescription")}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
          <iframe
            src={pageUrl}
            title={title}
            className="h-64 w-full border-0"
            loading="lazy"
          />
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
            {t("dataset.embedIframe")}
          </p>
          <pre className="overflow-x-auto rounded-md bg-[var(--color-background-secondary)] p-3 text-xs">
            {iframeSnippet}
          </pre>
          <Button type="button" size="sm" variant="secondary" onClick={() => void onCopy("iframe", iframeSnippet)}>
            {copied === "iframe" ? t("dataset.embedCopied") : t("dataset.embedCopy")}
          </Button>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
            {t("dataset.embedApi")}
          </p>
          <pre className="overflow-x-auto rounded-md bg-[var(--color-background-secondary)] p-3 text-xs">
            {apiSnippet}
          </pre>
          <Button type="button" size="sm" variant="secondary" onClick={() => void onCopy("api", apiSnippet)}>
            {copied === "api" ? t("dataset.embedCopied") : t("dataset.embedCopy")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
