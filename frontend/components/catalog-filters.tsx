"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

interface CatalogFiltersProps {
  initialTag?: string;
  initialSort?: string;
  query?: string;
}

interface TagFacet {
  tag: string;
  count: number;
}

export function CatalogFilters({
  initialTag = "",
  initialSort = "-published_at",
  query = "",
}: CatalogFiltersProps) {
  const router = useRouter();
  const [tag, setTag] = useState(initialTag);
  const [sort, setSort] = useState(initialSort);
  const [facets, setFacets] = useState<TagFacet[]>([]);

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/datasets/facets/tags`);
        if (!response.ok) {
          return;
        }
        const body = (await response.json()) as { data: TagFacet[] };
        setFacets(body.data.slice(0, 12));
      } catch {
        setFacets([]);
      }
    })();
  }, []);

  function applyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (query) {
      params.set("q", query);
    }
    const trimmedTag = tag.trim();
    if (trimmedTag) {
      params.set("tag", trimmedTag);
    }
    if (sort && sort !== "-published_at") {
      params.set("sort", sort);
    }
    const path = query ? "/portal" : "/portal";
    const queryString = params.toString();
    router.push(queryString ? `${path}?${queryString}` : path);
  }

  function clearFilters() {
    setTag("");
    setSort("-published_at");
    const params = new URLSearchParams();
    if (query) {
      params.set("q", query);
    }
    const queryString = params.toString();
    router.push(queryString ? `/portal?${queryString}` : "/portal");
  }

  return (
    <form
      onSubmit={applyFilters}
      className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-background-secondary)]/40 p-4"
    >
      <div className="min-w-[10rem] flex-1">
        <label htmlFor="catalog-tag" className="mb-1 block text-xs font-medium text-[var(--color-foreground-muted)]">
          Tag
        </label>
        <Input
          id="catalog-tag"
          value={tag}
          onChange={(event) => setTag(event.target.value)}
          placeholder="e.g. finance"
          aria-label="Filter by tag"
        />
      </div>
      <div className="min-w-[10rem]">
        <label htmlFor="catalog-sort" className="mb-1 block text-xs font-medium text-[var(--color-foreground-muted)]">
          Sort by
        </label>
        <select
          id="catalog-sort"
          value={sort}
          onChange={(event) => setSort(event.target.value)}
          className="h-10 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
        >
          <option value="-published_at">Recently published</option>
          <option value="title">Title (A–Z)</option>
          <option value="-title">Title (Z–A)</option>
          <option value="-quality_score">Quality score</option>
        </select>
      </div>
      <Button type="submit" size="sm">
        Apply filters
      </Button>
      <Button type="button" variant="secondary" size="sm" onClick={clearFilters}>
        Clear
      </Button>
      {facets.length > 0 ? (
        <div className="flex w-full flex-wrap gap-2 pt-1">
          {facets.map((facet) => (
            <button
              key={facet.tag}
              type="button"
              className={`rounded-full border px-2 py-0.5 text-xs ${
                tag === facet.tag
                  ? "border-[var(--color-primary)] bg-[var(--color-primary)] text-white"
                  : "border-[var(--color-border)] bg-[var(--color-background)]"
              }`}
              onClick={() => setTag(facet.tag)}
            >
              {facet.tag} ({facet.count})
            </button>
          ))}
        </div>
      ) : null}
    </form>
  );
}
