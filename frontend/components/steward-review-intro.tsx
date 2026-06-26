"use client";

import { useTranslation } from "react-i18next";

import { StewardGovernanceExport } from "@/components/steward-governance-export";
import { StewardQueueExport } from "@/components/steward-queue-export";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";

export interface GovernanceSummary {
  pending_review: number;
  pending_approval: number;
  changes_requested: number;
  sla_breached: number;
  published_last_30_days: number;
}

interface StewardReviewIntroProps {
  summary: GovernanceSummary | null;
  loadError: string | null;
  empty: boolean;
}

export function StewardReviewIntro({ summary, loadError, empty }: StewardReviewIntroProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("steward.title")}
        description={t("steward.subtitle")}
        actions={
          summary ? (
            <div className="flex flex-wrap items-center gap-3">
              <StewardGovernanceExport />
              <StewardQueueExport />
            </div>
          ) : undefined
        }
      />

      {loadError ? (
        <p role="alert" className="text-sm text-[var(--color-danger)]">
          {loadError.includes("403") ? t("steward.accessRequired") : loadError}
        </p>
      ) : null}

      {summary ? (
        <StatGrid>
          <StatCard label={t("steward.pendingReview")} value={summary.pending_review} />
          <StatCard label={t("steward.pendingApproval")} value={summary.pending_approval} />
          <StatCard label={t("steward.changesRequested")} value={summary.changes_requested} />
          <StatCard label={t("steward.slaBreached")} value={summary.sla_breached} />
          <StatCard label={t("steward.published30d")} value={summary.published_last_30_days} />
        </StatGrid>
      ) : null}

      {!loadError && empty ? <EmptyState title={t("steward.empty")} /> : null}
    </div>
  );
}
