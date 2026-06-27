"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function CatalogSearch({
  initialQuery = "",
  tag,
  sort,
}: {
  initialQuery?: string;
  tag?: string;
  sort?: string;
}) {
  const router = useRouter();
  const { t } = useTranslation();
  const [query, setQuery] = useState(initialQuery);

  function buildCatalogPath(nextQuery: string) {
    const trimmed = nextQuery.trim();
    const params = new URLSearchParams();
    if (trimmed) {
      params.set("q", trimmed);
    }
    if (tag) {
      params.set("tag", tag);
    }
    if (sort && sort !== "-published_at") {
      params.set("sort", sort);
    }
    const queryString = params.toString();
    return queryString ? `/portal?${queryString}` : "/portal";
  }

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(buildCatalogPath(query));
  }

  function onClear() {
    setQuery("");
    router.push(buildCatalogPath(""));
  }

  return (
    <form onSubmit={onSubmit} className="mb-6 flex flex-wrap gap-2">
      <Input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t("catalog.searchPlaceholder")}
        aria-label={t("catalog.searchPlaceholder")}
        className="min-w-[12rem] flex-1"
      />
      <Button type="submit">{t("catalog.search")}</Button>
      {query.trim() ? (
        <Button type="button" variant="secondary" onClick={onClear}>
          {t("catalog.clear")}
        </Button>
      ) : null}
    </form>
  );
}
