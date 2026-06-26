"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { EmbargoScheduler } from "@/components/embargo-scheduler";
import { LineageGraph } from "@/components/lineage-graph";
import { ReviewActions } from "@/components/review-actions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDatasetClient, getDatasetDataClient, getLineageClient } from "@/lib/api/client";
import type { Dataset, LineageEdge, LineageNode, WorkflowSubmission } from "@/lib/api/types";
import { formatStatusLabel, statusBadgeVariant } from "@/lib/dataset-display";

interface StewardSubmissionDrawerProps {
  submission: WorkflowSubmission;
  open: boolean;
  onClose: () => void;
}

export function StewardSubmissionDrawer({
  submission,
  open,
  onClose,
}: StewardSubmissionDrawerProps) {
  const { t } = useTranslation();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [lineageNodes, setLineageNodes] = useState<LineageNode[]>([]);
  const [lineageEdges, setLineageEdges] = useState<LineageEdge[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    void (async () => {
      setLoadError(null);
      try {
        const detail = await getDatasetClient(submission.dataset_id);
        setDataset(detail.data);
        try {
          const dataBody = await getDatasetDataClient(submission.dataset_id, 20);
          setPreviewRows(dataBody.data);
        } catch {
          setPreviewRows([]);
        }
        try {
          const lineage = await getLineageClient(submission.dataset_id);
          setLineageNodes(lineage.data.nodes);
          setLineageEdges(lineage.data.edges);
        } catch {
          setLineageNodes([]);
          setLineageEdges([]);
        }
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : t("steward.card.failedLoad"));
      }
    })();
  }, [open, submission.dataset_id, t]);

  const columns =
    dataset?.schema_snapshot?.columns?.map((column) => column.name) ||
    (previewRows[0] ? Object.keys(previewRows[0]) : []);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label={t("steward.drawer.close")}
        onClick={onClose}
      />
      <aside
        className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-[var(--color-border)] bg-[var(--color-background)] shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="steward-drawer-title"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-[var(--color-border)] bg-[var(--color-background)] p-4">
          <div>
            <h2 id="steward-drawer-title" className="text-lg font-semibold">
              {dataset?.title ?? t("steward.drawer.title")}
            </h2>
            <p className="text-sm text-[var(--color-foreground-muted)]">
              {t("steward.card.submission", { id: submission.id.slice(0, 8) })}
            </p>
          </div>
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>
            {t("steward.drawer.close")}
          </Button>
        </div>

        <div className="space-y-6 p-4">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[var(--color-foreground-muted)]">{t("steward.drawer.status")}</dt>
              <dd>{formatStatusLabel(submission.status)}</dd>
            </div>
            <div>
              <dt className="text-[var(--color-foreground-muted)]">{t("steward.drawer.submittedAt")}</dt>
              <dd>{new Date(submission.submitted_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-[var(--color-foreground-muted)]">{t("steward.drawer.reviewDue")}</dt>
              <dd>
                {submission.review_due_at
                  ? new Date(submission.review_due_at).toLocaleString()
                  : t("steward.card.sla.none")}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--color-foreground-muted)]">{t("steward.drawer.slaBreached")}</dt>
              <dd>{submission.sla_breached ? t("steward.drawer.yes") : t("steward.drawer.no")}</dd>
            </div>
          </dl>

          {submission.maker_notes ? (
            <div className="text-sm">
              <p className="font-medium">{t("steward.card.publisherNotes")}</p>
              <p className="mt-1 text-[var(--color-foreground-secondary)]">{submission.maker_notes}</p>
            </div>
          ) : null}

          {loadError ? (
            <p className="text-sm text-[var(--color-danger)]" role="alert">
              {loadError}
            </p>
          ) : null}

          {dataset ? (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                <Badge variant={statusBadgeVariant(dataset.status)}>
                  {formatStatusLabel(dataset.status)}
                </Badge>
                {dataset.quality_score != null ? (
                  <Badge variant="info">
                    {t("steward.card.quality", { score: Math.round(dataset.quality_score) })}
                  </Badge>
                ) : null}
              </div>
              <p className="text-[var(--color-foreground-secondary)]">
                {dataset.description || t("steward.card.noDescription")}
              </p>
              <Link href={`/portal/datasets/${dataset.id}`} className="underline">
                {t("steward.card.openDataset")}
              </Link>
            </div>
          ) : null}

          {columns.length > 0 ? (
            <div className="overflow-x-auto rounded border border-[var(--color-border)]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-[var(--color-background-secondary)]">
                    {columns.slice(0, 6).map((column) => (
                      <th key={column} className="px-2 py-1 text-left font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, index) => (
                    <tr key={index}>
                      {columns.slice(0, 6).map((column) => (
                        <td key={column} className="border-t border-[var(--color-border)] px-2 py-1">
                          {String(row[column] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {lineageNodes.length > 0 ? (
            <LineageGraph nodes={lineageNodes} edges={lineageEdges} />
          ) : null}

          <EmbargoScheduler datasetId={submission.dataset_id} />
          <ReviewActions submissionId={submission.id} />
        </div>
      </aside>
    </div>
  );
}
