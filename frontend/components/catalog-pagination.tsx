import Link from "next/link";

import { Button } from "@/components/ui/button";

interface CatalogPaginationProps {
  hasMore: boolean;
  nextCursor: string | null;
  totalCount: number;
  currentCount: number;
  basePath?: string;
  searchParams: Record<string, string | undefined>;
}

function buildHref(
  basePath: string,
  searchParams: Record<string, string | undefined>,
  cursor?: string,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (value && key !== "cursor") {
      params.set(key, value);
    }
  }
  if (cursor) {
    params.set("cursor", cursor);
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

export function CatalogPagination({
  hasMore,
  nextCursor,
  totalCount,
  currentCount,
  basePath = "/portal",
  searchParams,
}: CatalogPaginationProps) {
  const hasPrevious = Boolean(searchParams.cursor);

  return (
    <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-[var(--color-border)] pt-6">
      <p className="text-sm text-[var(--color-foreground-secondary)]">
        Showing {currentCount} of {totalCount.toLocaleString()} published datasets
      </p>
      <div className="flex gap-2">
        {hasPrevious ? (
          <Button variant="secondary" size="sm" asChild>
            <Link href={buildHref(basePath, { ...searchParams, cursor: undefined })}>
              Back to first page
            </Link>
          </Button>
        ) : null}
        {hasMore && nextCursor ? (
          <Button size="sm" asChild>
            <Link href={buildHref(basePath, searchParams, nextCursor)}>Next page</Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
