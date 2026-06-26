/** Staff surface navigation — single source for AppShell sidebars. */

export type StaffSurface = "publisher" | "steward" | "admin" | "developer";

export interface NavItem {
  href: string;
  labelKey: string;
}

export const SURFACE_NAV: Record<StaffSurface, NavItem[]> = {
  publisher: [
    { href: "/portal/dashboard", labelKey: "nav.dashboard" },
    { href: "/portal/publish", labelKey: "nav.publish" },
    { href: "/portal/notifications", labelKey: "nav.notifications" },
    { href: "/portal", labelKey: "nav.catalog" },
  ],
  steward: [
    { href: "/portal/review", labelKey: "steward.navReview" },
    { href: "/portal/approval", labelKey: "steward.navApproval" },
    { href: "/portal", labelKey: "nav.catalog" },
  ],
  admin: [
    { href: "/admin", labelKey: "admin.nav.overview" },
    { href: "/admin/branding", labelKey: "admin.nav.branding" },
    { href: "/admin/health", labelKey: "admin.nav.health" },
    { href: "/admin/connectors", labelKey: "admin.nav.connectors" },
    { href: "/admin/jobs", labelKey: "admin.nav.jobs" },
    { href: "/admin/security", labelKey: "admin.nav.security" },
    { href: "/portal", labelKey: "nav.catalog" },
  ],
  developer: [
    { href: "/developer", labelKey: "developer.nav.overview" },
    { href: "/developer/api-keys", labelKey: "developer.nav.apiKeys" },
    { href: "/developer/webhooks", labelKey: "developer.nav.webhooks" },
    { href: "/developer/explorer", labelKey: "developer.nav.openapi" },
    { href: "/developer/sdk", labelKey: "developer.nav.sdk" },
    { href: "/portal", labelKey: "nav.catalog" },
  ],
};

export const SURFACE_TITLE_KEYS: Record<StaffSurface, string> = {
  publisher: "publisher.shellTitle",
  steward: "steward.shellTitle",
  admin: "admin.shellTitle",
  developer: "developer.shellTitle",
};
