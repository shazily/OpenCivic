"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { getDownloadUrlClient, recordDatasetDownload } from "@/lib/api/client";
import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

type DownloadFormat = "csv" | "json" | "parquet";

interface DatasetDownloadProps {
  datasetId: string;
  title: string;
  rowCount: number | null;
}

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function safeFilename(title: string): string {
  return title.replace(/[^\w.-]+/g, "_").slice(0, 120) || "dataset";
}

export function DatasetDownload({ datasetId, title, rowCount }: DatasetDownloadProps) {
  const { t } = useTranslation();
  const [format, setFormat] = useState<DownloadFormat>("csv");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRows = async (): Promise<Record<string, unknown>[]> => {
    const token = getAccessToken();
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const pageSize = rowCount && rowCount > 0 ? Math.min(rowCount, 5000) : 5000;
    const response = await fetch(
      `${API_BASE}/datasets/${datasetId}/data?page_size=${pageSize}`,
      { headers },
    );
    if (!response.ok) {
      throw new Error(t("dataset.downloadFailed", { status: response.status }));
    }
    const body = (await response.json()) as { data: Record<string, unknown>[] };
    return body.data;
  };

  const downloadClientFormat = async (selected: "csv" | "json") => {
    const rows = await fetchRows();
    if (rows.length === 0) {
      throw new Error(t("dataset.downloadEmpty"));
    }
    const filename = safeFilename(title);
    if (selected === "csv") {
      const columns = Object.keys(rows[0]);
      const lines = [
        columns.join(","),
        ...rows.map((row) =>
          columns.map((col) => JSON.stringify(row[col] ?? "")).join(","),
        ),
      ];
      downloadBlob(`${filename}.csv`, lines.join("\n"), "text/csv");
      await recordDatasetDownload(datasetId, "csv");
      return;
    }
    downloadBlob(`${filename}.json`, JSON.stringify(rows, null, 2), "application/json");
    await recordDatasetDownload(datasetId, "json");
  };

  const downloadParquet = async () => {
    const { data } = await getDownloadUrlClient(datasetId, "parquet");
    window.open(data.url, "_blank", "noopener,noreferrer");
    await recordDatasetDownload(datasetId, "parquet");
  };

  const onDownload = async () => {
    setLoading(true);
    setError(null);
    try {
      if (format === "parquet") {
        await downloadParquet();
      } else {
        await downloadClientFormat(format);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("dataset.downloadFailedGeneric"));
    } finally {
      setLoading(false);
    }
  };

  if (!rowCount) {
    return null;
  }

  const statusLabel =
    format === "parquet"
      ? loading
        ? t("dataset.downloadOpening")
        : null
      : loading
        ? t("dataset.downloadPreparing")
        : null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-[var(--color-foreground-secondary)]">
            {t("dataset.downloadFormat")}
          </span>
          <select
            value={format}
            onChange={(event) => setFormat(event.target.value as DownloadFormat)}
            disabled={loading}
            className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
            aria-label={t("dataset.downloadFormat")}
          >
            <option value="csv">{t("dataset.downloadCsv")}</option>
            <option value="json">{t("dataset.downloadJson")}</option>
            <option value="parquet">{t("dataset.downloadParquet")}</option>
          </select>
        </label>
        <Button type="button" size="sm" disabled={loading} onClick={() => void onDownload()}>
          <Download className="h-4 w-4" />
          {loading ? t("dataset.downloading") : t("dataset.download")}
        </Button>
      </div>
      {statusLabel ? (
        <p className="text-xs text-[var(--color-foreground-muted)]" aria-live="polite">
          {statusLabel}
        </p>
      ) : null}
      {error ? (
        <p className="text-xs text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
