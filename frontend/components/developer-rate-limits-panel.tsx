"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";

export interface RateLimitGauge {
  api_key_id: string;
  name: string;
  key_prefix: string;
  limit_per_minute: number;
  used_last_minute: number;
  remaining: number;
  utilization_pct: number;
}

interface DeveloperRateLimitsPanelProps {
  gauges: RateLimitGauge[];
  tenantLimitPerMinute: number;
}

function gaugeVariant(pct: number): string {
  if (pct >= 90) {
    return "bg-[var(--color-danger)]";
  }
  if (pct >= 70) {
    return "bg-[var(--color-warning)]";
  }
  return "bg-[var(--color-primary)]";
}

export function DeveloperRateLimitsPanel({
  gauges,
  tenantLimitPerMinute,
}: DeveloperRateLimitsPanelProps) {
  const { t } = useTranslation();

  const totalUsed = gauges.reduce((sum, gauge) => sum + gauge.used_last_minute, 0);
  const highestUtil = gauges.reduce((max, gauge) => Math.max(max, gauge.utilization_pct), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("developer.rateLimits.title")}
        description={t("developer.rateLimits.description")}
        actions={
          <Link href="/developer" className="text-sm text-[var(--color-foreground-secondary)] hover:underline">
            ← {t("developer.nav.overview")}
          </Link>
        }
      />

      <StatGrid>
        <StatCard label={t("developer.rateLimits.tenantLimit")} value={tenantLimitPerMinute} />
        <StatCard label={t("developer.rateLimits.activeKeys")} value={gauges.length} />
        <StatCard label={t("developer.rateLimits.totalUsed")} value={totalUsed} />
        <StatCard
          label={t("developer.rateLimits.peakUtilization")}
          value={`${highestUtil}%`}
        />
      </StatGrid>

      {gauges.length === 0 ? (
        <EmptyState
          title={t("developer.rateLimits.empty")}
          description={t("developer.rateLimits.emptyDescription")}
        />
      ) : (
        <ul className="space-y-4">
          {gauges.map((gauge) => (
            <li
              key={gauge.api_key_id}
              className="rounded-lg border border-[var(--color-border)] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">{gauge.name}</p>
                  <p className="text-xs text-[var(--color-foreground-muted)]">
                    {gauge.key_prefix}…
                  </p>
                </div>
                <p className="text-sm tabular-nums">
                  {gauge.used_last_minute} / {gauge.limit_per_minute} {t("developer.rateLimits.perMin")}
                </p>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--color-background-secondary)]">
                <div
                  className={`h-full ${gaugeVariant(gauge.utilization_pct)}`}
                  style={{ width: `${Math.min(100, gauge.utilization_pct)}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-[var(--color-foreground-muted)]">
                {t("developer.rateLimits.remaining", {
                  count: gauge.remaining,
                  pct: gauge.utilization_pct,
                })}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
