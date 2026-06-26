"use client";

import { useTranslation } from "react-i18next";

import { DatasetCard } from "@/components/dataset-card";
import type { Dataset } from "@/lib/api/types";

interface CatalogFeaturedStripProps {
  datasets: Dataset[];
}

export function CatalogFeaturedStrip({ datasets }: CatalogFeaturedStripProps) {
  const { t } = useTranslation();

  if (datasets.length === 0) {
    return null;
  }

  return (
    <section className="mb-8" aria-labelledby="catalog-featured-heading">
      <div className="mb-4">
        <h2 id="catalog-featured-heading" className="text-lg font-semibold">
          {t("catalog.featuredTitle")}
        </h2>
        <p className="text-sm text-[var(--color-foreground-secondary)]">
          {t("catalog.featuredSubtitle")}
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {datasets.map((dataset) => (
          <DatasetCard key={dataset.id} dataset={dataset} showStatus={false} />
        ))}
      </div>
    </section>
  );
}
