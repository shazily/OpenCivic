"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { NotificationBell } from "@/components/notification-bell";
import { LanguageSwitcher } from "@/components/language-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";

interface StaffHeaderProps {
  title: string;
  links: { href: string; label: string }[];
}

const NAV_LABEL_KEYS: Record<string, string> = {
  "/portal": "nav.catalog",
  "/portal/dashboard": "nav.dashboard",
  "/portal/publish": "nav.publish",
  "/portal/notifications": "nav.notifications",
  "/portal/review": "steward.navReview",
  "/developer": "developer.nav.overview",
  "/developer/api-keys": "developer.nav.apiKeys",
};

export function StaffHeader({ title, links }: StaffHeaderProps) {
  const { t } = useTranslation();
  const { role, signOut } = useAuth();
  const router = useRouter();

  const handleSignOut = () => {
    signOut();
    router.push("/login");
  };

  return (
    <header className="border-b border-[var(--color-border)] bg-[var(--color-background)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div className="flex items-center gap-4">
          <Link href="/portal" className="text-lg font-bold">
            OpenCivic
          </Link>
          <span className="text-sm text-[var(--color-foreground-muted)]">{title}</span>
          {role ? (
            <span className="rounded-full bg-[var(--color-background-secondary)] px-2 py-0.5 text-xs capitalize">
              {role.replace("_", " ")}
            </span>
          ) : null}
        </div>
        <nav className="flex flex-wrap items-center gap-2 text-sm">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-[var(--color-foreground-secondary)] hover:text-[var(--color-foreground)]"
            >
              {t(NAV_LABEL_KEYS[link.href] ?? link.label)}
            </Link>
          ))}
          <NotificationBell />
          <LanguageSwitcher />
          <ThemeToggle />
          <Button type="button" variant="ghost" size="sm" onClick={handleSignOut}>
            {t("nav.signOut")}
          </Button>
        </nav>
      </div>
    </header>
  );
}
