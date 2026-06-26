"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100/api/v1";

export function StewardQueueExport() {
  const { t } = useTranslation();
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stewardToken = (): string | null => {
    return (
      getAccessToken() ||
      process.env.NEXT_PUBLIC_STEWARD_AUTH_TOKEN ||
      process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN ||
      null
    );
  };

  const onExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const token = stewardToken();
      const response = await fetch(`${API_BASE}/workflow/queue/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const json = (await response.json()) as {
        data?: { content: string; filename: string };
        errors?: { message: string }[];
      };
      if (!response.ok) {
        throw new Error(json.errors?.[0]?.message || `Export failed (${response.status})`);
      }
      const { content, filename } = json.data ?? {};
      if (!content || !filename) {
        throw new Error("Invalid export response");
      }
      const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button type="button" onClick={() => void onExport()} disabled={exporting} variant="secondary" size="sm">
        {exporting ? t("steward.queueExport.exporting") : t("steward.queueExport.button")}
      </Button>
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
