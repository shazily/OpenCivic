"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100/api/v1";

const REPORT_DAYS_OPTIONS = [7, 30, 90] as const;

export function StewardGovernanceExport() {
  const { t } = useTranslation();
  const [exporting, setExporting] = useState<"csv" | "pdf" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState<(typeof REPORT_DAYS_OPTIONS)[number]>(30);

  const stewardToken = (): string | null => {
    return (
      getAccessToken() ||
      process.env.NEXT_PUBLIC_STEWARD_AUTH_TOKEN ||
      process.env.NEXT_PUBLIC_DEV_AUTH_TOKEN ||
      null
    );
  };

  const onExport = async (format: "csv" | "pdf") => {
    setExporting(format);
    setError(null);
    try {
      const token = stewardToken();
      const response = await fetch(
        `${API_BASE}/workflow/governance/export?days=${days}&format=${format}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      const json = (await response.json()) as {
        data?: {
          content?: string;
          content_base64?: string;
          filename: string;
        };
        errors?: { message: string }[];
      };
      if (!response.ok) {
        throw new Error(json.errors?.[0]?.message || `Export failed (${response.status})`);
      }
      const payload = json.data;
      if (!payload?.filename) {
        throw new Error("Invalid export response");
      }
      if (format === "pdf" && payload.content_base64) {
        const binary = atob(payload.content_base64);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
          bytes[index] = binary.charCodeAt(index);
        }
        const blob = new Blob([bytes], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = payload.filename;
        anchor.click();
        URL.revokeObjectURL(url);
      } else if (payload.content) {
        const blob = new Blob([payload.content], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = payload.filename;
        anchor.click();
        URL.revokeObjectURL(url);
      } else {
        throw new Error("Invalid export response");
      }
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Export failed");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 text-sm text-[var(--color-foreground-secondary)]">
        <span>{t("steward.export.rangeLabel")}</span>
        <select
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-2 py-1 text-sm"
          value={days}
          onChange={(event) => setDays(Number(event.target.value) as (typeof REPORT_DAYS_OPTIONS)[number])}
          aria-label={t("steward.export.rangeLabel")}
        >
          {REPORT_DAYS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {t("steward.export.rangeDays", { days: option })}
            </option>
          ))}
        </select>
      </label>
      <Button
        type="button"
        onClick={() => void onExport("csv")}
        disabled={exporting !== null}
        variant="secondary"
        size="sm"
      >
        {exporting === "csv" ? t("steward.export.exporting") : t("steward.export.button")}
      </Button>
      <Button
        type="button"
        onClick={() => void onExport("pdf")}
        disabled={exporting !== null}
        variant="ghost"
        size="sm"
      >
        {exporting === "pdf" ? t("steward.export.exporting") : t("steward.export.buttonPdf")}
      </Button>
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
