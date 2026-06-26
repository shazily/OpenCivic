"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/layout/empty-state";
import { PageHeader } from "@/components/layout/page-header";

interface CatalogIntroProps {
  query: string;
  tag?: string;
  loadError: string | null;
  isEmpty: boolean;
}

export function CatalogIntro({ query, tag, loadError, isEmpty }: CatalogIntroProps) {
  const { t } = useTranslation();

  return (
    <>
      <a href="#main-content" className="skip-to-content">
        {t("catalog.skipToContent")}
      </a>
      <PageHeader title={t("catalog.title")} description={t("catalog.subtitle")} />

      {query ? (
        <p className="mb-6 text-sm text-[var(--color-foreground-secondary)]">
          {t("catalog.searchResults", { query })}
          {tag ? t("catalog.tagFilter", { tag }) : ""}
        </p>
      ) : null}

      {loadError ? (
        <p className="mb-6 text-sm text-[var(--color-danger)]" role="alert">
          {t("catalog.loadError", { message: loadError })}
        </p>
      ) : null}

      {!loadError && isEmpty ? (
        <EmptyState
          title={query || tag ? t("catalog.noMatch") : t("catalog.empty")}
          description={
            !query && !tag ? (
              <>
                <Link href="/login?next=/portal/publish" className="underline">
                  {t("catalog.staffSignIn")}
                </Link>{" "}
                {t("catalog.staffSignInHint")}
              </>
            ) : undefined
          }
        />
      ) : null}
    </>
  );
}
