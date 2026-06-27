"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import { Badge } from "@/components/ui/badge";

interface PublicHomeHeroProps {
  publishedCount: number;
}

export function PublicHomeHero({ publishedCount }: PublicHomeHeroProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-8">
      <PageHeader
        title={t("home.title")}
        description={t("home.subtitle")}
      />

      <StatGrid>
        <StatCard label={t("home.publishedDatasets")} value={publishedCount} />
        <StatCard label={t("home.instantApi")} value={t("home.instantApiValue")} />
        <StatCard label={t("home.openLicence")} value={t("home.openLicenceValue")} />
      </StatGrid>

      <div className="flex flex-wrap gap-2">
        <Badge variant="info">{t("home.trustQuality")}</Badge>
        <Badge variant="success">{t("home.trustReviewed")}</Badge>
        <Badge variant="outline">{t("home.trustMachineReadable")}</Badge>
      </div>

      <p className="text-sm text-[var(--color-foreground-secondary)]">
        <Link href="/login" className="underline">
          {t("catalog.staffSignIn")}
        </Link>{" "}
        {t("catalog.staffSignInHint")}
      </p>

      <div className="pt-2 text-center">
        <Link
          href="/portal"
          className="inline-flex items-center justify-center rounded-md bg-[var(--color-primary)] px-6 py-3 text-sm font-medium text-white hover:opacity-90"
        >
          {t("home.browseCatalog")}
        </Link>
      </div>
    </div>
  );
}
