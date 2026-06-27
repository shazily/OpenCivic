"use client";

import { useTranslation } from "react-i18next";

interface DeveloperPageHeaderProps {
  titleKey: string;
  descriptionKey: string;
  error?: string | null;
}

export function DeveloperPageHeader({ titleKey, descriptionKey, error }: DeveloperPageHeaderProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">{t(titleKey)}</h1>
      <p className="text-sm text-[var(--color-foreground-secondary)]">{t(descriptionKey)}</p>
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
