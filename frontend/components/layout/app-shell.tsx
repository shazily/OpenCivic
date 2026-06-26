"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";

import { useAuth } from "@/components/auth-provider";
import { LanguageSwitcher } from "@/components/language-switcher";
import { NotificationBell } from "@/components/notification-bell";
import { ThemeToggle } from "@/components/theme-toggle";
import { useTenantBranding } from "@/components/tenant-branding-provider";
import { Button } from "@/components/ui/button";
import type { NavItem, StaffSurface } from "@/lib/navigation/surfaces";
import { SURFACE_NAV, SURFACE_TITLE_KEYS } from "@/lib/navigation/surfaces";

interface AppShellProps {
  surface: StaffSurface;
  children: React.ReactNode;
}

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/portal" || href === "/admin" || href === "/developer") {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ surface, children }: AppShellProps) {
  const { t } = useTranslation();
  const pathname = usePathname();
  const router = useRouter();
  const { role, signOut } = useAuth();
  const { displayName, logoUrl } = useTenantBranding();
  const nav: NavItem[] = SURFACE_NAV[surface];
  const surfaceTitle = t(SURFACE_TITLE_KEYS[surface]);

  const handleSignOut = () => {
    signOut();
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-[var(--color-background-secondary)]">
      <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-background)]/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              href="/portal"
              className="flex items-center gap-2 text-base font-bold tracking-tight text-[var(--color-foreground)]"
            >
              {logoUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logoUrl} alt="" className="h-7 w-7 object-contain" />
              ) : null}
              <span className="truncate">{displayName}</span>
            </Link>
            <span className="hidden text-sm text-[var(--color-foreground-muted)] sm:inline">
              {surfaceTitle}
            </span>
            {role ? (
              <span className="rounded-full bg-[var(--color-background-secondary)] px-2 py-0.5 text-xs capitalize text-[var(--color-foreground-secondary)]">
                {role.replace(/_/g, " ")}
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <NotificationBell />
            <LanguageSwitcher />
            <ThemeToggle />
            <Button type="button" variant="ghost" size="sm" onClick={handleSignOut}>
              {t("nav.signOut")}
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl gap-6 px-4 py-6 md:gap-8 md:px-6 md:py-8">
        <aside className="hidden w-52 shrink-0 lg:block">
          <nav className="sticky top-20 space-y-0.5" aria-label={surfaceTitle}>
            {nav.map((item) => {
              const active = isActivePath(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={[
                    "block rounded-md px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-[var(--color-background)] font-medium text-[var(--color-foreground)] shadow-sm"
                      : "text-[var(--color-foreground-secondary)] hover:bg-[var(--color-background)] hover:text-[var(--color-foreground)]",
                  ].join(" ")}
                >
                  {t(item.labelKey)}
                </Link>
              );
            })}
          </nav>
        </aside>
        <main id="main-content" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}
