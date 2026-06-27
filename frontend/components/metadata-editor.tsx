"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { suggestMetadataClient, updateDatasetMetadata } from "@/lib/api/client";
import type { Dataset } from "@/lib/api/types";

interface MetadataEditorProps {
  dataset: Dataset;
  onSaved?: (dataset: Dataset) => void;
}

export function MetadataEditor({ dataset, onSaved }: MetadataEditorProps) {
  const editable = dataset.status === "draft" || dataset.status === "changes_requested";
  const [title, setTitle] = useState(dataset.title);
  const [description, setDescription] = useState(dataset.description ?? "");
  const [tags, setTags] = useState(dataset.tags.join(", "));
  const meta = dataset.metadata ?? {};
  const [publisher, setPublisher] = useState(String(meta["dct:publisher"] ?? meta.publisher ?? ""));
  const [theme, setTheme] = useState(String(meta["dcat:theme"] ?? meta.theme ?? ""));
  const [language, setLanguage] = useState(String(meta["dct:language"] ?? meta.language ?? "en"));
  const [licenseUrl, setLicenseUrl] = useState(String(meta["dct:license"] ?? meta.license ?? ""));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!editable) {
    return null;
  }

  async function handleSuggest() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await suggestMetadataClient(dataset.id);
      const data = response.data;
      if (typeof data.description === "string") {
        setDescription(data.description);
      }
      if (Array.isArray(data.tags)) {
        setTags(data.tags.join(", "));
      }
      const suggestedMeta = data.metadata as Record<string, string> | undefined;
      if (suggestedMeta) {
        setPublisher(String(suggestedMeta["dct:publisher"] ?? suggestedMeta.publisher ?? publisher));
        setTheme(String(suggestedMeta["dcat:theme"] ?? suggestedMeta.theme ?? theme));
        setLanguage(String(suggestedMeta["dct:language"] ?? suggestedMeta.language ?? language));
        setLicenseUrl(String(suggestedMeta["dct:license"] ?? suggestedMeta.license ?? licenseUrl));
      }
      setMessage(data.ai_assisted ? "AI suggestions applied — review and save." : "Suggestions applied — review and save.");
    } catch (suggestError) {
      setError(suggestError instanceof Error ? suggestError.message : "Suggest failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await updateDatasetMetadata(dataset.id, {
        title: title.trim(),
        description: description.trim() || undefined,
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        metadata: {
          "dct:publisher": publisher.trim() || undefined,
          "dcat:theme": theme.trim() || undefined,
          "dct:language": language.trim() || undefined,
          "dct:license": licenseUrl.trim() || undefined,
          "dcat:title": title.trim(),
        },
      });
      setMessage("Metadata saved.");
      onSaved?.(response.data);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mb-8 rounded-lg border border-[var(--color-border)] p-4">
      <h2 className="mb-4 text-lg font-semibold">Edit metadata</h2>
      <div className="mb-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={() => void handleSuggest()}
        >
          {busy ? "Suggesting…" : "AI suggest metadata"}
        </Button>
        <span className="text-xs text-[var(--color-foreground-muted)] self-center">
          AI-assisted. Verify before publishing.
        </span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-1 sm:col-span-2">
          <span className="text-sm font-medium">Title</span>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label className="grid gap-1 sm:col-span-2">
          <span className="text-sm font-medium">Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
          />
        </label>
        <label className="grid gap-1 sm:col-span-2">
          <span className="text-sm font-medium">Tags (comma-separated)</span>
          <Input value={tags} onChange={(e) => setTags(e.target.value)} />
        </label>
        <label className="grid gap-1">
          <span className="text-sm font-medium">Publisher (DCAT)</span>
          <Input value={publisher} onChange={(e) => setPublisher(e.target.value)} />
        </label>
        <label className="grid gap-1">
          <span className="text-sm font-medium">Theme (DCAT)</span>
          <Input value={theme} onChange={(e) => setTheme(e.target.value)} />
        </label>
        <label className="grid gap-1">
          <span className="text-sm font-medium">Language</span>
          <Input value={language} onChange={(e) => setLanguage(e.target.value)} />
        </label>
        <label className="grid gap-1 sm:col-span-2">
          <span className="text-sm font-medium">Licence URL</span>
          <Input value={licenseUrl} onChange={(e) => setLicenseUrl(e.target.value)} />
        </label>
      </div>
      {error ? (
        <p className="mt-3 text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="mt-3 text-sm text-[var(--color-foreground-secondary)]">{message}</p> : null}
      <Button type="button" className="mt-4" disabled={busy} onClick={() => void handleSave()}>
        {busy ? "Saving…" : "Save metadata"}
      </Button>
    </section>
  );
}
