import { PublicHeader } from "@/components/public-header";
import { CatalogFeaturedStrip } from "@/components/catalog-featured-strip";
import { CatalogFilters } from "@/components/catalog-filters";
import { SemanticSearchBanner } from "@/components/semantic-search-banner";
import { CatalogIntro } from "@/components/catalog-intro";
import { CatalogPagination } from "@/components/catalog-pagination";
import { CatalogSearch } from "@/components/catalog-search";
import { DatasetCard } from "@/components/dataset-card";
import {
  listPublicDatasetsServer,
  searchPublicDatasetsServer,
} from "@/lib/api/server";

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams?: {
    q?: string;
    cursor?: string;
    tag?: string;
    sort?: string;
  };
}

export default async function PortalPage({ searchParams }: PageProps) {
  const query = searchParams?.q?.trim() || "";
  const tag = searchParams?.tag?.trim() || undefined;
  const sort = searchParams?.sort || undefined;
  const cursor = searchParams?.cursor || undefined;

  let datasets: Awaited<ReturnType<typeof listPublicDatasetsServer>>["data"] = [];
  let featured: Awaited<ReturnType<typeof listPublicDatasetsServer>>["data"] = [];
  let meta: Awaited<ReturnType<typeof listPublicDatasetsServer>>["meta"] = {
    has_more: false,
    next_cursor: null,
    total_count: 0,
  };
  let loadError: string | null = null;

  try {
    const response = query
      ? await searchPublicDatasetsServer(query, { cursor, tag, pageSize: 12 })
      : await listPublicDatasetsServer({ cursor, tag, sort, pageSize: 12 });
    datasets = response.data;
    meta = response.meta;

    if (!query && !tag && !cursor) {
      const featuredResponse = await listPublicDatasetsServer({
        sort: "-quality_score",
        pageSize: 3,
      });
      featured = featuredResponse.data;
    }
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Failed to load datasets";
  }

  return (
    <>
      <PublicHeader />
      <main id="main-content" className="mx-auto max-w-6xl px-6 py-8">
        <CatalogIntro
          query={query}
          tag={tag}
          loadError={loadError}
          isEmpty={!loadError && datasets.length === 0}
        />

        <CatalogSearch initialQuery={query} tag={tag} sort={sort} />
        <SemanticSearchBanner />
        <CatalogFilters initialTag={tag} initialSort={sort ?? "-published_at"} query={query} />

        {!query && !tag ? <CatalogFeaturedStrip datasets={featured} /> : null}

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {datasets.map((dataset) => (
            <DatasetCard key={dataset.id} dataset={dataset} showStatus={false} />
          ))}
        </div>

        {!loadError && datasets.length > 0 ? (
          <CatalogPagination
            hasMore={meta.has_more}
            nextCursor={meta.next_cursor}
            totalCount={meta.total_count}
            currentCount={datasets.length}
            searchParams={{ q: query || undefined, tag, sort, cursor }}
          />
        ) : null}
      </main>
    </>
  );
}
