"use client";

import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import type { DeepHealth } from "@/lib/api/admin";

interface AdminHealthPanelProps {
  health: DeepHealth | null;
  error: string | null;
}

export function AdminHealthPanel({ health, error }: AdminHealthPanelProps) {
  const { t } = useTranslation();

  const okChecks = health
    ? Object.values(health.checks).filter((status) => status === "ok").length
    : 0;
  const totalChecks = health ? Object.keys(health.checks).length : 0;
  const failingChecks = health
    ? Object.entries(health.checks).filter(([, status]) => status !== "ok")
    : [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("admin.health.title")}
        description={t("admin.health.description")}
      />

      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}

      {health ? (
        <>
          <StatGrid>
            <StatCard label={t("admin.health.overallStatus")} value={health.status} />
            <StatCard label={t("admin.health.checksPassing")} value={`${okChecks}/${totalChecks}`} />
            <StatCard label={t("admin.health.deployment")} value={health.deployment_mode} />
            <StatCard label={t("admin.health.version")} value={health.version} />
            <StatCard label={t("admin.health.aiMode")} value={health.ai_mode} />
          </StatGrid>

          {failingChecks.length > 0 ? (
            <p className="text-sm text-[var(--color-foreground-secondary)]">
              {t("admin.health.failingCount", { count: failingChecks.length })}
            </p>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(health.checks).map(([name, status]) => (
              <StatCard
                key={name}
                label={name.replace(/_/g, " ")}
                value={status}
              />
            ))}
          </div>
        </>
      ) : !error ? (
        <EmptyState title={t("admin.health.empty")} />
      ) : null}
    </div>
  );
}
