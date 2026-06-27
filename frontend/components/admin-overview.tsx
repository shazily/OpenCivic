"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/page-header";
import type { AdminOverview, OrgUsageSummary } from "@/lib/api/admin";

interface AdminOverviewViewProps {
  overview: AdminOverview | null;
  orgUsage: OrgUsageSummary | null;
  error: string | null;
}

export function AdminOverviewView({ overview, orgUsage, error }: AdminOverviewViewProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("admin.overview.title")}
        description={t("admin.overview.description")}
      />
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      {overview ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(overview.health).map(([key, value]) => (
              <Card key={key}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium capitalize text-[var(--color-foreground-muted)]">
                    {key}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Badge variant={value === "ok" ? "success" : "danger"}>{value}</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
          {orgUsage ? (
            <section>
              <h2 className="mb-3 text-lg font-semibold">{t("admin.overview.tenantUsage")}</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-[var(--color-foreground-muted)]">
                      {t("admin.overview.users")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">{orgUsage.user_count}</CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-[var(--color-foreground-muted)]">
                      {t("admin.overview.datasets")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">
                    {t("admin.overview.published", {
                      published: orgUsage.published_count,
                      total: orgUsage.dataset_count,
                    })}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-[var(--color-foreground-muted)]">
                      {t("admin.overview.apiCalls")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">{orgUsage.api_calls}</CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-[var(--color-foreground-muted)]">
                      {t("admin.overview.downloads")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-2xl font-semibold">{orgUsage.downloads}</CardContent>
                </Card>
              </div>
            </section>
          ) : null}
          <p className="text-sm text-[var(--color-foreground-secondary)]">
            {t("admin.overview.deployment")}: <strong>{overview.deployment_mode}</strong> ·{" "}
            {t("admin.overview.version")}: <strong>{overview.version}</strong> ·{" "}
            {t("admin.overview.backup")}: {overview.backup_status}
            {overview.backup_verified_at
              ? ` (${t("admin.overview.verified", {
                  date: new Date(overview.backup_verified_at).toLocaleString(),
                })})`
              : ""}
            {overview.backup_message ? ` — ${overview.backup_message}` : ""} ·{" "}
            {t("admin.overview.securityEvents")}: {overview.security_events_count}
          </p>
          <section>
            <h2 className="mb-3 text-lg font-semibold">{t("admin.overview.connectors")}</h2>
            {overview.connectors.length === 0 ? (
              <p className="text-sm text-[var(--color-foreground-muted)]">
                {t("admin.overview.noConnectors")}{" "}
                <Link href="/admin/connectors" className="underline">
                  {t("admin.overview.viewMatrix")}
                </Link>
              </p>
            ) : (
              <ul className="space-y-2">
                {overview.connectors.map((connector) => (
                  <li
                    key={connector.id}
                    className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-4 py-3 text-sm"
                  >
                    {connector.name} — {connector.status} ({connector.circuit_state})
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
