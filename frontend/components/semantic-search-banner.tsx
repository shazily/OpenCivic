"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

export function SemanticSearchBanner() {
  const { t } = useTranslation();
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/portal/capabilities`, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          return;
        }
        const body = (await response.json()) as {
          data: { semantic_search_degraded?: boolean };
        };
        setDegraded(Boolean(body.data.semantic_search_degraded));
      } catch {
        setDegraded(true);
      }
    })();
  }, []);

  if (!degraded) {
    return null;
  }

  return (
    <div
      className="mb-6 rounded-lg border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-4 py-3 text-sm"
      role="status"
    >
      {t("catalog.semanticDegraded")}
    </div>
  );
}
