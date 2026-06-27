import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import ar from "./locales/ar.json";
import en from "./locales/en.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import zh from "./locales/zh.json";

const STORAGE_KEY = "opencivic_locale";

export type AppLanguage = "en" | "ar" | "fr" | "es" | "zh";

const RTL_LANGUAGES: AppLanguage[] = ["ar"];

function initialLanguage(): string {
  if (typeof window === "undefined") {
    return "en";
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "ar" || stored === "fr" || stored === "es" || stored === "zh") {
    return stored;
  }
  return "en";
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ar: { translation: ar },
    fr: { translation: fr },
    es: { translation: es },
    zh: { translation: zh },
  },
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setAppLanguage(code: AppLanguage): void {
  i18n.changeLanguage(code);
  if (typeof document !== "undefined") {
    document.documentElement.lang = code;
    document.documentElement.dir = RTL_LANGUAGES.includes(code) ? "rtl" : "ltr";
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, code);
  }
}

export default i18n;
