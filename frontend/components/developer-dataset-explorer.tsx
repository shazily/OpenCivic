"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/layout/empty-state";
import { LoadingBlock } from "@/components/layout/loading-block";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard, StatGrid } from "@/components/layout/stat-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100/api/v1";

interface DeveloperDatasetExplorerProps {
  datasetId?: string;
}

type ExplorerTab = "openapi" | "odata";

type OpenApiSpec = {
  openapi?: string;
  info?: { title?: string; version?: string };
  paths?: Record<string, unknown>;
};

type ODataService = {
  odata_version?: string;
  service_root?: string;
  entity_set?: string;
  metadata_url?: string;
  example_filter?: string;
};

export function DeveloperDatasetExplorer({ datasetId }: DeveloperDatasetExplorerProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<ExplorerTab>("openapi");
  const [spec, setSpec] = useState<OpenApiSpec | null>(null);
  const [odata, setOdata] = useState<ODataService | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(datasetId));

  const globalDocsUrl =
    process.env.NEXT_PUBLIC_API_URL?.replace("/api/v1", "/docs") || "http://localhost:8100/docs";

  const authHeaders = (): Record<string, string> => {
    const token = getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  useEffect(() => {
    if (!datasetId) {
      return;
    }
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE}/datasets/${datasetId}/openapi.json`, {
          headers: authHeaders(),
        });
        const json = await response.json();
        if (!response.ok) {
          throw new Error(json.errors?.[0]?.message || `Failed (${response.status})`);
        }
        setSpec(json.data as OpenApiSpec);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load OpenAPI");
      } finally {
        setLoading(false);
      }
    })();
  }, [datasetId]);

  const loadOData = async () => {
    if (!datasetId || odata || loading) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/datasets/${datasetId}/odata`, {
        headers: authHeaders(),
      });
      const json = await response.json();
      if (!response.ok) {
        throw new Error(json.errors?.[0]?.message || `Failed (${response.status})`);
      }
      setOdata(json.data as ODataService);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load OData");
    } finally {
      setLoading(false);
    }
  };

  const onTabChange = (next: ExplorerTab) => {
    setTab(next);
    setError(null);
    if (next === "odata") {
      void loadOData();
    }
  };

  if (!datasetId) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={t("developer.explorer.title")}
          description={t("developer.explorer.descriptionGlobal")}
        />
        <iframe
          title={t("developer.explorer.iframeTitle")}
          src={globalDocsUrl}
          className="h-[75vh] w-full rounded-lg border border-[var(--color-border)]"
        />
      </div>
    );
  }

  const pathCount = spec?.paths ? Object.keys(spec.paths).length : 0;
  const openapiUrl = `${API_BASE}/datasets/${datasetId}/openapi.json`;
  const entitySet = odata?.entity_set ?? "dataset";
  const serviceRoot = odata?.service_root ?? `${API_BASE}/datasets/${datasetId}/odata`;
  const odataExample = odata?.example_filter ?? `${serviceRoot}/${entitySet}?$top=100`;
  const powerQueryM = `let
    Source = OData.Feed("${serviceRoot}", null, [Implementation="2.0"]),
    Table = Source{[Name="${entitySet}", Signature="table"]}[Data]
in
    Table`;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("developer.explorer.titleDataset")}
        description={t("developer.explorer.descriptionDataset")}
        actions={
          <Button asChild variant="secondary" size="sm">
            <Link href={`/portal/datasets/${datasetId}`}>{t("developer.explorer.viewDataset")}</Link>
          </Button>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant={tab === "openapi" ? "default" : "secondary"}
          onClick={() => onTabChange("openapi")}
        >
          {t("developer.explorer.tabOpenApi")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant={tab === "odata" ? "default" : "secondary"}
          onClick={() => onTabChange("odata")}
        >
          {t("developer.explorer.tabOData")}
        </Button>
      </div>

      {loading ? <LoadingBlock message={t("developer.explorer.loading")} /> : null}
      {error ? (
        <p className="text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}

      {tab === "openapi" && !loading && !error && spec ? (
        <>
          <StatGrid>
            <StatCard label={t("developer.explorer.specVersion")} value={spec.openapi ?? "—"} />
            <StatCard label={t("developer.explorer.apiVersion")} value={spec.info?.version ?? "—"} />
            <StatCard label={t("developer.explorer.pathCount")} value={pathCount} />
          </StatGrid>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{spec.info?.title ?? datasetId}</CardTitle>
              <p className="text-xs text-[var(--color-foreground-muted)]">{openapiUrl}</p>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[60vh] overflow-auto rounded-lg bg-[var(--color-surface-muted)] p-4 text-xs">
                {JSON.stringify(spec, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </>
      ) : null}

      {tab === "odata" && !loading && !error && odata ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{t("dataset.apiExplorer.tabOData")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-[var(--color-foreground-secondary)]">
              {t("dataset.apiExplorer.odataVersion", { version: odata.odata_version ?? "4.0" })}
            </p>
            <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
              {odataExample}
            </pre>
            {odata.metadata_url ? (
              <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                {odata.metadata_url}
              </pre>
            ) : null}
            <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
              {t("dataset.apiExplorer.odataPowerQuery")}
            </p>
            <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
              {powerQueryM}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      {!loading && !error && tab === "openapi" && !spec ? (
        <EmptyState title={t("developer.explorer.empty")} />
      ) : null}
    </div>
  );
}
