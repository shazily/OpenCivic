"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/layout/empty-state";
import { LoadingBlock } from "@/components/layout/loading-block";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

interface NotificationItem {
  id: string;
  title: string;
  body: string;
  event_type: string;
  link?: string | null;
  read: boolean;
  created_at: string;
}

export default function NotificationsPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadNotifications = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setError(t("notifications.signInRequired"));
      setLoading(false);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/notifications/?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        throw new Error(`Failed to load notifications (${response.status})`);
      }
      const body = (await response.json()) as { data: NotificationItem[] };
      setItems(body.data);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("notifications.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadNotifications();
  }, [loadNotifications]);

  async function markRead(id: string) {
    const token = getAccessToken();
    if (!token) {
      return;
    }
    await fetch(`${API_BASE}/notifications/${id}/read`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, read: true } : item)),
    );
  }

  async function markAllRead() {
    const token = getAccessToken();
    if (!token) {
      return;
    }
    await fetch(`${API_BASE}/notifications/read-all`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    setItems((current) => current.map((item) => ({ ...item, read: true })));
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title={t("notifications.title")}
        actions={
          <Button type="button" variant="secondary" size="sm" onClick={() => void markAllRead()}>
            {t("notifications.markAllRead")}
          </Button>
        }
      />
      {loading ? <LoadingBlock message={t("notifications.loading")} /> : null}
      {error ? <p className="text-sm text-[var(--color-danger)]">{error}</p> : null}
      {!loading && !error && items.length === 0 ? (
        <EmptyState title={t("notifications.empty")} />
      ) : null}
      <ul className="grid gap-3">
          {items.map((item) => (
            <li
              key={item.id}
              className={`rounded-lg border border-[var(--color-border)] p-4 ${
                item.read ? "opacity-70" : "bg-[var(--color-background-secondary)]"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="mt-1 text-sm text-[var(--color-foreground-secondary)]">{item.body}</p>
                  <p className="mt-2 text-xs text-[var(--color-foreground-muted)]">
                    {new Date(item.created_at).toLocaleString()} · {item.event_type}
                  </p>
                  {item.link ? (
                    <Link href={item.link} className="mt-2 inline-block text-sm underline">
                      {t("notifications.viewDetails")}
                    </Link>
                  ) : null}
                </div>
                {!item.read ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => void markRead(item.id)}
                  >
                    {t("notifications.markRead")}
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
    </div>
  );
}
