"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listFeedbackForDataset } from "@/lib/api/client";

interface FeedbackItem {
  id: string;
  dataset_id: string;
  type: string;
  rating: number | null;
  content: string | null;
  status: string;
  created_at: string;
}

interface PublisherFeedbackPanelProps {
  datasets: Array<{ id: string; title: string }>;
}

export function PublisherFeedbackPanel({ datasets }: PublisherFeedbackPanelProps) {
  const { t } = useTranslation();
  const [items, setItems] = useState<Array<FeedbackItem & { datasetTitle: string }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const published = datasets.slice(0, 5);
        const batches = await Promise.all(
          published.map(async (dataset) => {
            const response = await listFeedbackForDataset(dataset.id);
            return response.data.map((item) => ({
              ...item,
              datasetTitle: dataset.title,
            }));
          }),
        );
        const merged = batches
          .flat()
          .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
          .slice(0, 8);
        setItems(merged);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [datasets]);

  if (loading) {
    return <p className="text-sm text-[var(--color-foreground-muted)]">{t("publisher.feedback.loading")}</p>;
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("publisher.feedback.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[var(--color-foreground-muted)]">
            {t("publisher.feedback.empty")}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("publisher.feedback.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="rounded-md border border-[var(--color-border)] p-3 text-sm"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{item.datasetTitle}</span>
              {item.rating ? (
                <Badge variant="info">{t("publisher.feedback.stars", { count: item.rating })}</Badge>
              ) : null}
              <Badge variant="outline">{item.status}</Badge>
            </div>
            {item.content ? (
              <p className="mt-2 text-[var(--color-foreground-secondary)]">{item.content}</p>
            ) : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
