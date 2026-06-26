"use client";

import { useEffect } from "react";
import { I18nextProvider } from "react-i18next";

import i18n, { setAppLanguage, type AppLanguage } from "@/lib/i18n";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const code: AppLanguage = i18n.language.startsWith("ar")
      ? "ar"
      : i18n.language.startsWith("fr")
        ? "fr"
        : i18n.language.startsWith("es")
          ? "es"
          : i18n.language.startsWith("zh")
            ? "zh"
            : "en";
    setAppLanguage(code);
  }, []);

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}
