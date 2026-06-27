"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

import { LanguageSwitcher } from "@/components/language-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { useTenantBranding } from "@/components/tenant-branding-provider";
import { Button } from "@/components/ui/button";

export function PublicHeader() {
  const { t } = useTranslation();
  const { displayName, logoUrl } = useTenantBranding();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-background)]/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <Link
          href="/portal"
          className="flex items-center gap-2 text-lg font-bold tracking-tight text-[var(--color-foreground)]"
        >
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoUrl} alt="" className="h-8 w-8 object-contain" />
          ) : null}
          {displayName}
        </Link>
        <nav className="flex items-center gap-2 text-sm md:gap-4">
          <Link
            href="/portal"
            className="hidden text-[var(--color-foreground-secondary)] hover:text-[var(--color-foreground)] sm:inline"
          >
            {t("public.catalog")}
          </Link>
          <LanguageSwitcher />
          <ThemeToggle />
          <Button asChild variant="secondary" size="sm">
            <Link href="/login">{t("public.staffSignIn")}</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
