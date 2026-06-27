"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/layout/page-header";
import { createDataset, getDatasetClient, uploadDatasetFile } from "@/lib/api/client";
import { getAccessToken } from "@/lib/auth/session";
import { createTusSession, uploadFileWithTus } from "@/lib/upload/tus-upload";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";
const TUS_THRESHOLD_BYTES = 5 * 1024 * 1024;

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export default function PublishPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tusEndpoint, setTusEndpoint] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      return;
    }
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/datasets/upload/tus-config`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          return;
        }
        const body = (await response.json()) as {
          data: { enabled: boolean; endpoint: string | null };
        };
        if (body.data.enabled && body.data.endpoint) {
          setTusEndpoint(body.data.endpoint);
        }
      } catch {
        setTusEndpoint(null);
      }
    })();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError(t("publish.chooseFile"));
      return;
    }

    setBusy(true);
    setError(null);
    setStatus(t("publish.creating"));

    try {
      const created = await createDataset({
        title,
        slug: slug || slugify(title),
        description: description || undefined,
      });
      const datasetId = created.data.id;

      if (tusEndpoint && file.size >= TUS_THRESHOLD_BYTES) {
        setStatus(t("publish.uploadingTus", { percent: 0 }));
        const session = await createTusSession(datasetId, file.name);
        await uploadFileWithTus(file, session, (percent) => {
          setStatus(t("publish.uploadingTus", { percent }));
        });
      } else {
        setStatus(t("publish.uploading"));
        await uploadDatasetFile(datasetId, file);
      }

      setStatus(t("publish.processing"));
      for (let attempt = 0; attempt < 30; attempt += 1) {
        const polled = await getDatasetClient(datasetId);
        if (polled.data.row_count) {
          router.push(`/portal/datasets/${datasetId}`);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }

      setStatus(t("publish.queued"));
      router.push(`/portal/datasets/${datasetId}`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : t("publish.failed"));
      setStatus(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title={t("publish.title")} description={t("publish.description")} />
        <Card>
          <CardHeader>
            <CardTitle className="sr-only">{t("publish.title")}</CardTitle>
            {tusEndpoint ? (
              <CardDescription>
                {t("publish.tusHint", { endpoint: tusEndpoint })}
              </CardDescription>
            ) : null}
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="grid gap-4">
              <label className="grid gap-1">
                <span className="text-sm font-medium">{t("publish.titleLabel")}</span>
                <Input
                  required
                  value={title}
                  onChange={(event) => {
                    setTitle(event.target.value);
                    if (!slug) {
                      setSlug(slugify(event.target.value));
                    }
                  }}
                />
              </label>

              <label className="grid gap-1">
                <span className="text-sm font-medium">{t("publish.slugLabel")}</span>
                <Input
                  required
                  value={slug}
                  onChange={(event) => setSlug(slugify(event.target.value))}
                  pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
                />
              </label>

              <label className="grid gap-1">
                <span className="text-sm font-medium">{t("publish.descriptionLabel")}</span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={3}
                  className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                />
              </label>

              <label className="grid gap-1">
                <span className="text-sm font-medium">{t("publish.fileLabel")}</span>
                <input
                  required
                  type="file"
                  accept=".csv,.tsv,.json,.jsonl,.xlsx,.parquet,text/csv,text/tab-separated-values,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </label>

              {error ? (
                <p role="alert" className="text-sm text-[var(--color-danger)]">
                  {error}
                </p>
              ) : null}
              {status ? <p aria-live="polite" className="text-sm">{status}</p> : null}

              <Button type="submit" disabled={busy}>
                {busy ? t("publish.submitting") : t("publish.submit")}
              </Button>
            </form>
          </CardContent>
        </Card>
    </div>
  );
}
