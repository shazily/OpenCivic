"use client";

import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import type { DatasetConnectorStatus } from "@/lib/api/types";
import { formatStatusLabel } from "@/lib/dataset-display";

interface DatasetConnectorChipProps {
  connector: DatasetConnectorStatus;
}

export function DatasetConnectorChip({ connector }: DatasetConnectorChipProps) {
  const { t } = useTranslation();

  const variant =
    connector.status === "error" || connector.circuit_state === "open"
      ? "danger"
      : connector.status === "paused"
        ? "warning"
        : "info";

  const lastSync = connector.last_sync_at
    ? new Date(connector.last_sync_at).toLocaleString()
    : t("dataset.connector.neverSynced");

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Badge variant={variant}>
        {t("dataset.connector.badge", { name: connector.name })}
      </Badge>
      <span className="text-[var(--color-foreground-muted)]">
        {t("dataset.connector.lastSync", { when: lastSync })}
      </span>
      {connector.sync_frequency ? (
        <span className="text-[var(--color-foreground-muted)]">
          {t("dataset.connector.frequency", {
            frequency: formatStatusLabel(connector.sync_frequency),
          })}
        </span>
      ) : null}
    </div>
  );
}
