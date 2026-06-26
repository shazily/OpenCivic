"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { ApprovalActions } from "@/components/approval-actions";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkflowSubmission } from "@/lib/api/types";

interface ApprovalQueuePanelProps {
  items: WorkflowSubmission[];
  loadError: string | null;
}

export function ApprovalQueuePanel({ items, loadError }: ApprovalQueuePanelProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("steward.approval.title")}
        description={t("steward.approval.description")}
      />

      {loadError ? (
        <p role="alert" className="text-sm text-[var(--color-danger)]">
          {loadError.includes("403")
            ? t("steward.approval.accessRequired")
            : loadError}
        </p>
      ) : null}

      {!loadError && items.length === 0 ? (
        <EmptyState title={t("steward.approval.empty")} />
      ) : null}

      <div className="grid gap-4">
        {items.map((item) => (
          <Card key={item.id}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                {t("steward.approval.submission", { id: item.id.slice(0, 8) })}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm">
                <Link href={`/portal/datasets/${item.dataset_id}`} className="underline">
                  {t("steward.approval.viewDataset")}
                </Link>
              </p>
              {item.checker_notes ? (
                <p className="text-sm text-[var(--color-foreground-secondary)]">
                  {t("steward.approval.stewardNotes", { notes: item.checker_notes })}
                </p>
              ) : null}
              <Badge variant="warning">{t("steward.approval.pendingBadge")}</Badge>
              <ApprovalActions submissionId={item.id} />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
