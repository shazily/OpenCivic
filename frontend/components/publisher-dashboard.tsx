"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { DatasetCard } from "@/components/dataset-card";
import { EmptyState } from "@/components/layout/empty-state";
import { LoadingBlock } from "@/components/layout/loading-block";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import { PublisherFeedbackPanel } from "@/components/publisher-feedback-panel";
import { PublisherStalenessBanner } from "@/components/publisher-staleness-banner";
import { PublisherWorkflowTimeline } from "@/components/publisher-workflow-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { listMyDatasets, getPublisherSummaryClient } from "@/lib/api/client";
import type { Dataset } from "@/lib/api/types";
import { formatStatusLabel, statusBadgeVariant } from "@/lib/dataset-display";

export function PublisherDashboard() {
  const { t } = useTranslation();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [summary, setSummary] = useState<{
    dataset_count: number;
    published_count: number;
    views: number;
    downloads: number;
    api_calls: number;
    ai_queries: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const [response, analytics] = await Promise.all([
          listMyDatasets(),
          getPublisherSummaryClient(),
        ]);
        setDatasets(response.data);
        setSummary(analytics.data);
      } catch (loadError) {
        setError(
          loadError instanceof Error ? loadError.message : t("publisher.dashboard.loadFailed"),
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  const byStatus = datasets.reduce<Record<string, number>>((acc, dataset) => {
    acc[dataset.status] = (acc[dataset.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-8">
      <PageHeader
        title={t("publisher.dashboard.title")}
        description={t("publisher.dashboard.description")}
        actions={
          <Button asChild>
            <Link href="/portal/publish">{t("publisher.dashboard.publishNew")}</Link>
          </Button>
        }
      />

      {loading ? <LoadingBlock message={t("publisher.dashboard.loading")} /> : null}
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}

      {!loading && !error ? (
        <>
          {summary ? (
            <StatGrid>
              <StatCard label={t("admin.overview.datasets")} value={summary.dataset_count} />
              <StatCard
                label={t("admin.overview.published", {
                  published: summary.published_count,
                  total: summary.dataset_count,
                })}
                value={summary.published_count}
              />
              <StatCard label={t("admin.overview.apiCalls")} value={summary.api_calls} />
              <StatCard label={t("admin.overview.downloads")} value={summary.downloads} />
              <StatCard label={t("publisher.dashboard.views")} value={summary.views} />
              <StatCard label={t("publisher.dashboard.aiQueries")} value={summary.ai_queries} />
            </StatGrid>
          ) : null}

          <PublisherStalenessBanner datasets={datasets} />

          {Object.keys(byStatus).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(byStatus).map(([status, count]) => (
                <Badge key={status} variant={statusBadgeVariant(status)}>
                  {formatStatusLabel(status)}: {count}
                </Badge>
              ))}
            </div>
          ) : null}

          {datasets.length === 0 ? (
            <EmptyState
              title={t("publisher.dashboard.empty")}
              description={t("publisher.dashboard.emptyDescription")}
              action={
                <Button asChild>
                  <Link href="/portal/publish">{t("publisher.dashboard.publishNew")}</Link>
                </Button>
              }
            />
          ) : (
            <section>
              <h2 className="mb-4 text-lg font-semibold">{t("publisher.dashboard.yourDatasets")}</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                {datasets.map((dataset) => (
                  <DatasetCard key={dataset.id} dataset={dataset} showStatus />
                ))}
              </div>
            </section>
          )}

          <PublisherFeedbackPanel
            datasets={datasets
              .filter((dataset) => dataset.status === "published")
              .map((dataset) => ({ id: dataset.id, title: dataset.title }))}
          />

          <PublisherWorkflowTimeline />
        </>
      ) : null}
    </div>
  );
}
