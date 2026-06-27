"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

interface PaletteHit {
  id: string;
  title: string;
  slug: string;
  type: string;
  tier?: "keyword" | "semantic";
}

export function CommandPalette() {
  const { t } = useTranslation();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<PaletteHit[]>([]);
  const [loading, setLoading] = useState(false);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setHits([]);
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") {
        close();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [close]);

  useEffect(() => {
    if (!open || query.trim().length < 2) {
      setHits([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void (async () => {
        setLoading(true);
        try {
          const response = await fetch(
            `${API_BASE}/search/palette?q=${encodeURIComponent(query.trim())}`,
            { signal: controller.signal },
          );
          if (!response.ok) {
            return;
          }
          const body = (await response.json()) as { data: PaletteHit[] };
          setHits(body.data);
        } catch {
          setHits([]);
        } finally {
          setLoading(false);
        }
      })();
    }, 150);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [open, query]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-[12vh]"
      role="presentation"
      onClick={close}
    >
      <div
        className="w-full max-w-lg rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] shadow-xl"
        role="dialog"
        aria-label={t("search.paletteLabel")}
        onClick={(event) => event.stopPropagation()}
      >
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("search.palettePlaceholder")}
          className="w-full border-b border-[var(--color-border)] bg-transparent px-4 py-3 text-sm outline-none"
        />
        <ul className="max-h-72 overflow-y-auto py-2">
          {loading ? (
            <li className="px-4 py-2 text-sm text-[var(--color-foreground-muted)]">
              {t("search.searching")}
            </li>
          ) : null}
          {!loading && hits.length === 0 && query.trim().length >= 2 ? (
            <li className="px-4 py-2 text-sm text-[var(--color-foreground-muted)]">
              {t("search.noResults")}
            </li>
          ) : null}
          {hits.map((hit) => (
            <li key={hit.id}>
              <button
                type="button"
                className="flex w-full flex-col items-start px-4 py-2 text-left text-sm hover:bg-[var(--color-background-secondary)]"
                onClick={() => {
                  router.push(`/portal/datasets/${hit.id}`);
                  close();
                }}
              >
                <span className="flex items-center gap-2 font-medium">
                  {hit.title}
                  {hit.tier === "semantic" || hit.type === "related" ? (
                    <span className="rounded bg-[var(--color-background-secondary)] px-1.5 py-0.5 text-xs font-normal text-[var(--color-foreground-muted)]">
                      {t("search.related")}
                    </span>
                  ) : (
                    <span className="rounded bg-[var(--color-background-secondary)] px-1.5 py-0.5 text-xs font-normal text-[var(--color-foreground-muted)]">
                      {t("search.exactMatch")}
                    </span>
                  )}
                </span>
                <span className="text-xs text-[var(--color-foreground-muted)]">{hit.slug}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="border-t border-[var(--color-border)] px-4 py-2 text-xs text-[var(--color-foreground-muted)]">
          {t("search.paletteHint")}
        </p>
      </div>
    </div>
  );
}
