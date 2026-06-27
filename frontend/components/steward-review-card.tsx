"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { EmbargoScheduler } from "@/components/embargo-scheduler";
import { LineageGraph } from "@/components/lineage-graph";
import { ReviewActions } from "@/components/review-actions";
import { StewardSubmissionDrawer } from "@/components/steward-submission-drawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getDatasetClient, getDatasetDataClient, getLineageClient } from "@/lib/api/client";
import type { Dataset, LineageEdge, LineageNode, WorkflowSubmission } from "@/lib/api/types";
import { formatStatusLabel, statusBadgeVariant } from "@/lib/dataset-display";
import type { TFunction } from "i18next";

function slaState(
  dueAt: string | null,
  slaBreached: boolean | undefined,
): "none" | "breached" | "urgent" | "ok" {
  if (slaBreached) {
    return "breached";
  }
  if (!dueAt) {
    return "none";
  }
  const minutesLeft = Math.round((new Date(dueAt).getTime() - Date.now()) / (1000 * 60));
  if (minutesLeft < 0) {
    return "breached";
  }
  if (minutesLeft <= 120) {
    return "urgent";
  }
  return "ok";
}

function slaLabel(dueAt: string | null, t: TFunction): string {
  if (!dueAt) {
    return t("steward.card.sla.none");
  }
  const due = new Date(dueAt);
  const now = new Date();
  const minutesLeft = Math.round((due.getTime() - now.getTime()) / (1000 * 60));
  if (minutesLeft < 0) {
    const hours = Math.abs(Math.round(minutesLeft / 60));
    return t("steward.card.sla.breached", { hours });
  }
  if (minutesLeft < 60) {
    return t("steward.card.sla.minutes", { minutes: minutesLeft });
  }
  const hoursLeft = Math.round(minutesLeft / 60);
  return t("steward.card.sla.hours", { hours: hoursLeft });
}

function useSlaState(dueAt: string | null, slaBreached?: boolean) {
  const { t } = useTranslation();
  const [state, setState] = useState(() => ({
    label: slaLabel(dueAt, t),
    status: slaState(dueAt, slaBreached),
  }));
  useEffect(() => {
    const update = () =>
      setState({
        label: slaLabel(dueAt, t),
        status: slaState(dueAt, slaBreached),
      });
    update();
    const timer = window.setInterval(update, 60_000);
    return () => window.clearInterval(timer);
  }, [dueAt, slaBreached, t]);
  return state;
}

interface StewardReviewCardProps {
  submission: WorkflowSubmission;
}

export function StewardReviewCard({ submission }: StewardReviewCardProps) {
  const { t } = useTranslation();
  const { label: slaText, status: slaStatus } = useSlaState(
    submission.review_due_at,
    submission.sla_breached,
  );
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [lineageNodes, setLineageNodes] = useState<LineageNode[]>([]);
  const [lineageEdges, setLineageEdges] = useState<LineageEdge[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const detail = await getDatasetClient(submission.dataset_id);
        setDataset(detail.data);
        try {
          const dataBody = await getDatasetDataClient(submission.dataset_id, 5);
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
    }, [submission.dataset_id, t]);

  const columns =
    dataset?.schema_snapshot?.columns?.map((c) => c.name) ||
    (previewRows[0] ? Object.keys(previewRows[0]) : []);

  return (
    <Card
      className={
        slaStatus === "breached"
          ? "border-[var(--color-danger)] ring-1 ring-[var(--color-danger)]/30"
          : slaStatus === "urgent"
            ? "border-[var(--color-warning)]"
            : undefined
      }
    >
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">
              {dataset?.title ?? `Dataset ${submission.dataset_id}`}
            </CardTitle>
            <p className="mt-1 text-sm text-[var(--color-foreground-muted)]">
              {t("steward.card.submission", { id: submission.id.slice(0, 8) })}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant={
                slaStatus === "breached"
                  ? "danger"
                  : slaStatus === "urgent"
                    ? "warning"
                    : "info"
              }
              className={slaStatus === "breached" ? "animate-pulse" : undefined}
            >
              {slaText}
            </Badge>
            <Button type="button" size="sm" variant="secondary" onClick={() => setDrawerOpen(true)}>
              {t("steward.drawer.open")}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {submission.maker_notes ? (
          <p className="text-sm">
            <span className="font-medium">{t("steward.card.publisherNotes")}</span>{" "}
            {submission.maker_notes}
          </p>
        ) : null}

        {loadError ? (
          <p className="text-sm text-[var(--color-danger)]">{loadError}</p>
        ) : dataset ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-2 text-sm">
              <div className="flex flex-wrap gap-2">
                <Badge variant={statusBadgeVariant(dataset.status)}>
                  {formatStatusLabel(dataset.status)}
                </Badge>
                {dataset.quality_score != null ? (
                  <Badge variant="info">
                    {t("steward.card.quality", { score: Math.round(dataset.quality_score) })}
                  </Badge>
                ) : null}
                {dataset.row_count != null ? (
                  <span className="text-[var(--color-foreground-muted)]">
                    {t("steward.card.rows", { count: dataset.row_count })}
                  </span>
                ) : null}
              </div>
              <p className="text-[var(--color-foreground-secondary)]">
                {dataset.description || t("steward.card.noDescription")}
              </p>
              <Link
                href={`/portal/datasets/${dataset.id}`}
                className="text-sm underline"
              >
                {t("steward.card.openDataset")}
              </Link>
            </div>
            <div className="overflow-x-auto rounded border border-[var(--color-border)]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-[var(--color-background-secondary)]">
                    {columns.slice(0, 4).map((col) => (
                      <th key={col} className="px-2 py-1 text-left font-medium">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, i) => (
                    <tr key={i}>
                      {columns.slice(0, 4).map((col) => (
                        <td key={col} className="border-t border-[var(--color-border)] px-2 py-1">
                          {String(row[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <p className="text-sm text-[var(--color-foreground-muted)]">{t("steward.card.loading")}</p>
        )}

        {lineageNodes.length > 0 ? (
          <LineageGraph nodes={lineageNodes} edges={lineageEdges} />
        ) : null}

        <EmbargoScheduler datasetId={submission.dataset_id} />

        <ReviewActions submissionId={submission.id} />
      </CardContent>
      <StewardSubmissionDrawer
        submission={submission}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </Card>
  );
}
