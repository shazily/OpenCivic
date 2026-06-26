"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/layout/empty-state";
import { LoadingBlock } from "@/components/layout/loading-block";
import { PageHeader } from "@/components/layout/page-header";
import { getPublisherWorkflowTimelineClient } from "@/lib/api/client";

interface TimelineEvent {
  id: number;
  event_type: string;
  dataset_id: string;
  created_at: string;
}

function formatEventLabel(eventType: string): string {
  return eventType
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ");
}

export function PublisherWorkflowTimeline() {
  const { t } = useTranslation();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const response = await getPublisherWorkflowTimelineClient();
        setEvents(response.data);
      } catch (loadError) {
        setError(
          loadError instanceof Error ? loadError.message : t("publisher.timeline.loadFailed"),
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  return (
    <section className="space-y-4">
      <PageHeader
        title={t("publisher.timeline.title")}
        description={t("publisher.timeline.description")}
      />

      {loading ? <LoadingBlock message={t("publisher.timeline.loading")} /> : null}
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}

      {!loading && !error && events.length === 0 ? (
        <EmptyState title={t("publisher.timeline.empty")} />
      ) : null}

      {!loading && !error && events.length > 0 ? (
        <ol className="relative space-y-4 border-s border-[var(--color-border)] ps-4">
          {events.map((event) => (
            <li key={event.id} className="relative">
              <span className="absolute -start-[1.35rem] top-1.5 h-2.5 w-2.5 rounded-full bg-[var(--color-primary)]" />
              <div className="rounded-lg border border-[var(--color-border)] p-3">
                <p className="text-sm font-medium">{formatEventLabel(event.event_type)}</p>
                <p className="mt-1 text-xs text-[var(--color-foreground-muted)]">
                  {new Date(event.created_at).toLocaleString()} ·{" "}
                  <Link
                    href={`/portal/datasets/${event.dataset_id}`}
                    className="text-[var(--color-primary)] hover:underline"
                  >
                    {t("publisher.timeline.viewDataset")}
                  </Link>
                </p>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
