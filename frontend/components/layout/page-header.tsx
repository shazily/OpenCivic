import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

/** Consistent page title block for all Tier 1+ staff surfaces. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-foreground)] md:text-3xl">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm text-[var(--color-foreground-secondary)] md:text-base">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

interface PageHeaderLinkActionProps {
  href: string;
  label: string;
}

export function PageHeaderLinkAction({ href, label }: PageHeaderLinkActionProps) {
  return (
    <Button asChild>
      <Link href={href}>{label}</Link>
    </Button>
  );
}
