"use client";

import { useTranslation } from "react-i18next";

import { setAppLanguage, type AppLanguage } from "@/lib/i18n";

const LANGUAGES: AppLanguage[] = ["en", "ar", "fr", "es", "zh"];

function resolveLanguage(code: string): AppLanguage {
  const base = code.split("-")[0];
  if (base === "en" || base === "ar" || base === "fr" || base === "es" || base === "zh") {
    return base;
  }
  return "en";
}

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const current = resolveLanguage(i18n.language);

  return (
    <label className="inline-flex items-center gap-1 text-xs">
      <span className="sr-only">{t("language.label")}</span>
      <select
        aria-label={t("language.label")}
        className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-2 py-0.5 text-xs"
        value={current}
        onChange={(event) => setAppLanguage(event.target.value as AppLanguage)}
      >
        {LANGUAGES.map((code) => (
          <option key={code} value={code}>
            {t(`language.${code}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
