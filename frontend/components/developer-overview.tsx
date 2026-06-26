"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import { Button } from "@/components/ui/button";

interface DeveloperOverviewProps {
  keyCount: number;
  pythonSnippet: string;
}

export function DeveloperOverview({ keyCount, pythonSnippet }: DeveloperOverviewProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-8">
      <PageHeader
        title={t("developer.overview.title")}
        description={t("developer.overview.description")}
        actions={
          <Button asChild variant="secondary" size="sm">
            <Link href="/developer/api-keys">{t("developer.nav.apiKeys")}</Link>
          </Button>
        }
      />

      <StatGrid>
        <StatCard label={t("developer.nav.apiKeys")} value={keyCount} />
      </StatGrid>

      <nav className="flex flex-wrap gap-3 text-sm">
        <Link href="/developer/webhooks" className="text-[var(--color-primary)] hover:underline">
          {t("developer.nav.webhooks")}
        </Link>
        <Link href="/developer/explorer" className="text-[var(--color-primary)] hover:underline">
          {t("developer.nav.openapi")}
        </Link>
        <Link href="/developer/rate-limits" className="text-[var(--color-primary)] hover:underline">
          {t("developer.nav.rateLimits")}
        </Link>
      </nav>

      <section>
        <h2 className="mb-2 text-lg font-semibold">{t("developer.overview.quickStart")}</h2>
        <pre className="overflow-auto rounded-lg bg-[var(--color-background-secondary)] p-4 text-sm">
          {pythonSnippet}
        </pre>
      </section>
    </div>
  );
}
