"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import type { Dataset } from "@/lib/api/types";
import { formatStatusLabel, stalenessBadgeVariant } from "@/lib/dataset-display";

interface PublisherStalenessBannerProps {
  datasets: Dataset[];
}

export function PublisherStalenessBanner({ datasets }: PublisherStalenessBannerProps) {
  const { t } = useTranslation();

  const flagged = datasets.filter(
    (dataset) =>
      dataset.staleness_state === "stale" ||
      dataset.staleness_state === "possibly_outdated" ||
      dataset.staleness_state === "pending_refresh",
  );

  if (flagged.length === 0) {
    return null;
  }

  const staleCount = flagged.filter((dataset) => dataset.staleness_state === "stale").length;

  return (
    <div
      className="rounded-lg border border-[var(--color-warning)] bg-[var(--color-warning-muted)] p-4"
      role="status"
    >
      <p className="text-sm font-medium text-[var(--color-foreground)]">
        {t("publisher.staleness.title", { count: flagged.length })}
      </p>
      <p className="mt-1 text-sm text-[var(--color-foreground-secondary)]">
        {staleCount > 0
          ? t("publisher.staleness.descriptionStale", { stale: staleCount })
          : t("publisher.staleness.description")}
      </p>
      <ul className="mt-3 space-y-2">
        {flagged.slice(0, 5).map((dataset) => (
          <li key={dataset.id} className="flex flex-wrap items-center gap-2 text-sm">
            <Link
              href={`/portal/datasets/${dataset.id}`}
              className="font-medium text-[var(--color-primary)] hover:underline"
            >
              {dataset.title}
            </Link>
            <Badge variant={stalenessBadgeVariant(dataset.staleness_state)}>
              {formatStatusLabel(dataset.staleness_state)}
            </Badge>
          </li>
        ))}
      </ul>
      {flagged.length > 5 ? (
        <p className="mt-2 text-xs text-[var(--color-foreground-muted)]">
          {t("publisher.staleness.more", { count: flagged.length - 5 })}
        </p>
      ) : null}
    </div>
  );
}
