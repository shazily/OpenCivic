"use client";

import { useTranslation } from "react-i18next";

import { ConnectorCreateForm } from "@/components/connector-create-form";
import { ConnectorRowActions } from "@/components/connector-row-actions";
import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import { Badge } from "@/components/ui/badge";
import type { ConnectorListItem } from "@/lib/api/admin";

type Connector = ConnectorListItem;

interface AdminConnectorsPanelProps {
  connectors: Connector[];
  error: string | null;
}

export function AdminConnectorsPanel({ connectors, error }: AdminConnectorsPanelProps) {
  const { t } = useTranslation();

  const active = connectors.filter((item) => item.status === "active").length;
  const paused = connectors.filter((item) => item.status === "paused").length;
  const errored = connectors.filter((item) => item.status === "error").length;
  const openCircuits = connectors.filter((item) => item.circuit_state === "open").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("admin.connectors.title")}
        description={t("admin.connectors.description")}
      />

      <StatGrid>
        <StatCard label={t("admin.connectors.total")} value={connectors.length} />
        <StatCard label={t("admin.connectors.active")} value={active} />
        <StatCard label={t("admin.connectors.paused")} value={paused} />
        <StatCard label={t("admin.connectors.errored")} value={errored} />
        <StatCard label={t("admin.connectors.circuitOpen")} value={openCircuits} />
      </StatGrid>

      <ConnectorCreateForm />

      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}

      {connectors.length === 0 && !error ? (
        <EmptyState title={t("admin.connectors.empty")} />
      ) : null}

      {connectors.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--color-background-secondary)]">
              <tr>
                <th className="px-4 py-3 font-medium">{t("admin.connectors.name")}</th>
                <th className="px-4 py-3 font-medium">{t("admin.connectors.type")}</th>
                <th className="px-4 py-3 font-medium">{t("admin.connectors.status")}</th>
                <th className="px-4 py-3 font-medium">{t("admin.connectors.circuit")}</th>
                <th className="px-4 py-3 font-medium">{t("admin.connectors.lastSync")}</th>
                <th className="px-4 py-3 font-medium">{t("admin.connectors.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {connectors.map((item) => (
                <tr key={item.id} className="border-t border-[var(--color-border)]">
                  <td className="px-4 py-3">{item.name}</td>
                  <td className="px-4 py-3">{item.type}</td>
                  <td className="px-4 py-3">
                    <Badge variant={item.status === "active" ? "success" : "warning"}>
                      {item.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">{item.circuit_state}</td>
                  <td className="px-4 py-3 text-[var(--color-foreground-muted)]">
                    {item.last_sync_at
                      ? new Date(item.last_sync_at).toLocaleString()
                      : t("admin.connectors.neverSynced")}
                  </td>
                  <td className="px-4 py-3">
                    <ConnectorRowActions connectorId={item.id} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
