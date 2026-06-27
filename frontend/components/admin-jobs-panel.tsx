"use client";

import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { QueueDepthSparkline } from "@/components/queue-depth-sparkline";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import type { JobsSummary } from "@/lib/api/admin";

const CELERY_QUEUES = [
  { name: "critical", descriptionKey: "admin.jobs.queueCritical" },
  { name: "ingest", descriptionKey: "admin.jobs.queueIngest" },
  { name: "refresh", descriptionKey: "admin.jobs.queueRefresh" },
  { name: "ai", descriptionKey: "admin.jobs.queueAi" },
  { name: "notifications", descriptionKey: "admin.jobs.queueNotifications" },
  { name: "maintenance", descriptionKey: "admin.jobs.queueMaintenance" },
] as const;

interface AdminJobsPanelProps {
  flowerUrl: string;
  summary: JobsSummary | null;
  error: string | null;
}

export function AdminJobsPanel({ flowerUrl, summary, error }: AdminJobsPanelProps) {
  const { t } = useTranslation();

  const depthByName = new Map(
    (summary?.queues ?? []).map((queue) => [queue.name, queue.depth]),
  );
  const totalDepth = summary?.total_depth ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader title={t("admin.jobs.title")} description={t("admin.jobs.description")} />

      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}

      <StatGrid>
        <StatCard label={t("admin.jobs.queueCount")} value={CELERY_QUEUES.length} />
        <StatCard label={t("admin.jobs.totalDepth")} value={totalDepth} />
        <StatCard
          label={t("admin.jobs.workerCount")}
          value={summary?.worker_count ?? "—"}
        />
        <StatCard
          label={t("admin.jobs.dataSource")}
          value={
            summary?.source === "placeholder"
              ? t("admin.jobs.placeholder")
              : summary?.source ?? "—"
          }
        />
      </StatGrid>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CELERY_QUEUES.map((queue) => {
          const depth = depthByName.get(queue.name) ?? 0;
          const trend =
            summary?.queues.find((item) => item.name === queue.name)?.depth_trend ?? [];
          return (
            <div key={queue.name} className="space-y-2">
              <StatCard label={queue.name} value={depth} />
              {trend.length > 0 ? (
                <QueueDepthSparkline
                  points={trend}
                  label={t("admin.jobs.depthTrend", { queue: queue.name })}
                />
              ) : null}
            </div>
          );
        })}
      </div>

      {!summary && !error ? <EmptyState title={t("admin.jobs.empty")} /> : null}

      <iframe
        title={t("admin.jobs.flowerTitle")}
        src={flowerUrl}
        className="h-[70vh] w-full rounded-lg border border-[var(--color-border)] bg-white"
      />
    </div>
  );
}
