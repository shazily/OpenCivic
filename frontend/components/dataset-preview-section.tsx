"use client";

import { useTranslation } from "react-i18next";

interface DatasetPreviewSectionProps {
  columns: string[];
  rows: Record<string, unknown>[];
  dataError: string | null;
}

export function DatasetPreviewSection({ columns, rows, dataError }: DatasetPreviewSectionProps) {
  const { t } = useTranslation();

  return (
    <section aria-labelledby="dataset-preview-heading">
      <h2 id="dataset-preview-heading" className="mb-4 text-xl font-semibold">
        {t("dataset.previewTitle")}
      </h2>

      {dataError ? (
        <p className="text-sm text-[var(--color-foreground-muted)]" role="status">
          {dataError.includes("404") ? t("dataset.noDataYet") : dataError}
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-[var(--color-foreground-muted)]" role="status">
          {t("dataset.noDataYet")}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-[var(--color-background-secondary)] text-left">
                {columns.map((column) => (
                  <th
                    key={column}
                    className="border-b border-[var(--color-border)] px-3 py-2 font-medium"
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="even:bg-[var(--color-background-secondary)]/50">
                  {columns.map((column) => (
                    <td key={column} className="border-b border-[var(--color-border)] px-3 py-2">
                      {String(row[column] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
