"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { DatasetConnectorChip } from "@/components/dataset-connector-chip";
import { DatasetDownload } from "@/components/dataset-download";
import { DatasetStatsSparkline } from "@/components/dataset-stats-sparkline";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import { Badge } from "@/components/ui/badge";
import {
  formatStatusLabel,
  stalenessBadgeVariant,
  statusBadgeVariant,
} from "@/lib/dataset-display";
import type { Dataset, DatasetConnectorStatus } from "@/lib/api/types";

interface EngagementPoint {
  date: string;
  views: number;
  downloads: number;
  total: number;
}

interface DatasetStats {
  views?: number;
  downloads?: number;
  average_rating?: number | null;
}

interface DatasetDetailHeaderProps {
  dataset: Dataset;
  stats: DatasetStats | null;
  trend?: EngagementPoint[];
  connector?: DatasetConnectorStatus | null;
}

export function DatasetDetailHeader({
  dataset,
  stats,
  trend = [],
  connector = null,
}: DatasetDetailHeaderProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <Link
        href="/portal"
        className="inline-block text-sm text-[var(--color-foreground-secondary)] hover:text-[var(--color-foreground)]"
      >
        {t("dataset.backToCatalog")}
      </Link>

      <PageHeader
        title={dataset.title}
        description={dataset.description || t("dataset.noDescription")}
        actions={
          <DatasetDownload
            datasetId={dataset.id}
            title={dataset.slug}
            rowCount={dataset.row_count}
          />
        }
      />

      <div className="flex flex-wrap gap-2">
        <Badge variant={statusBadgeVariant(dataset.status)}>
          {formatStatusLabel(dataset.status)}
        </Badge>
        <Badge variant={stalenessBadgeVariant(dataset.staleness_state)}>
          {formatStatusLabel(dataset.staleness_state)}
        </Badge>
        {dataset.quality_score != null ? (
          <Badge variant="info">
            {t("dataset.quality", { score: Math.round(dataset.quality_score) })}
          </Badge>
        ) : null}
        <Badge variant="outline">{dataset.access_level}</Badge>
      </div>

      {connector ? <DatasetConnectorChip connector={connector} /> : null}

      <StatGrid>
        <StatCard
          label={t("dataset.rows")}
          value={dataset.row_count?.toLocaleString() ?? "—"}
        />
        <StatCard
          label={t("dataset.views")}
          value={stats?.views?.toLocaleString() ?? "—"}
        />
        <StatCard
          label={t("dataset.downloads")}
          value={stats?.downloads?.toLocaleString() ?? "—"}
        />
        <StatCard
          label={t("dataset.rating")}
          value={
            stats?.average_rating != null ? `${stats.average_rating.toFixed(1)} / 5` : "—"
          }
        />
      </StatGrid>

      {dataset.status === "published" && trend.length > 0 ? (
        <DatasetStatsSparkline
          points={trend}
          label={t("dataset.engagementTrend")}
        />
      ) : null}
    </div>
  );
}
