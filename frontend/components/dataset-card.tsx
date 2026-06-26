import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  formatStatusLabel,
  stalenessBadgeVariant,
  statusBadgeVariant,
} from "@/lib/dataset-display";
import type { Dataset } from "@/lib/api/types";

export function DatasetCard({
  dataset,
  showStatus = true,
}: {
  dataset: Dataset;
  showStatus?: boolean;
}) {
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">
          <Link
            href={`/portal/datasets/${dataset.id}`}
            className="hover:text-[var(--color-primary)]"
          >
            {dataset.title}
          </Link>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {dataset.description ? (
          <p className="line-clamp-2 text-sm text-[var(--color-foreground-secondary)]">
            {dataset.description}
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          {showStatus ? (
            <Badge variant={statusBadgeVariant(dataset.status)}>
              {formatStatusLabel(dataset.status)}
            </Badge>
          ) : null}
          <Badge variant={stalenessBadgeVariant(dataset.staleness_state)}>
            {formatStatusLabel(dataset.staleness_state)}
          </Badge>
          {dataset.quality_score != null ? (
            <Badge variant="info">Quality {Math.round(dataset.quality_score)}</Badge>
          ) : null}
          {dataset.row_count != null ? (
            <span className="text-xs text-[var(--color-foreground-muted)]">
              {dataset.row_count.toLocaleString()} rows
            </span>
          ) : null}
        </div>
        {dataset.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {dataset.tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
