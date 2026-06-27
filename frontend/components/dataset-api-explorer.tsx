"use client";

import Link from "next/link";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAccessToken } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8100/api/v1";

interface DatasetApiExplorerProps {
  datasetId: string;
  slug: string;
}

type ExplorerTab = "rest" | "openapi" | "odata";

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

export function DatasetApiExplorer({ datasetId, slug }: DatasetApiExplorerProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<ExplorerTab>("rest");
  const [copied, setCopied] = useState<string | null>(null);
  const [spec, setSpec] = useState<OpenApiSpec | null>(null);
  const [odata, setOdata] = useState<ODataService | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const dataUrl = `${API_BASE}/datasets/${datasetId}/data`;
  const openapiUrl = `${API_BASE}/datasets/${datasetId}/openapi.json`;
  const odataUrl = `${API_BASE}/datasets/${datasetId}/odata`;
  const curlData = `curl "${dataUrl}?page_size=100"`;
  const curlOpenApi = `curl "${openapiUrl}"`;
  const powershellData = `Invoke-RestMethod -Uri "${dataUrl}?page_size=100"`;

  const authHeaders = (): Record<string, string> => {
    const token = getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const onCopy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(null);
    }
  };

  const loadOpenApi = async () => {
    if (spec || loading) {
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const response = await fetch(openapiUrl, { headers: authHeaders() });
      const json = await response.json();
      if (!response.ok) {
        throw new Error(json.errors?.[0]?.message || `Failed (${response.status})`);
      }
      setSpec(json.data as OpenApiSpec);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Failed to load OpenAPI");
    } finally {
      setLoading(false);
    }
  };

  const loadOData = async () => {
    if (odata || loading) {
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const response = await fetch(odataUrl, { headers: authHeaders() });
      const json = await response.json();
      if (!response.ok) {
        throw new Error(json.errors?.[0]?.message || `Failed (${response.status})`);
      }
      setOdata(json.data as ODataService);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Failed to load OData");
    } finally {
      setLoading(false);
    }
  };

  const onTabChange = (next: ExplorerTab) => {
    setTab(next);
    setLoadError(null);
    if (next === "openapi") {
      void loadOpenApi();
    }
    if (next === "odata") {
      void loadOData();
    }
  };

  const pathCount = spec?.paths ? Object.keys(spec.paths).length : 0;
  const entitySet = odata?.entity_set ?? slug.replace(/-/g, "_");
  const serviceRoot = odata?.service_root ?? odataUrl;
  const odataExample =
    odata?.example_filter ?? `${serviceRoot}/${entitySet}?$top=100`;
  const powerQueryM = `let
    Source = OData.Feed("${serviceRoot}", null, [Implementation="2.0"]),
    Table = Source{[Name="${entitySet}", Signature="table"]}[Data]
in
    Table`;

  return (
    <Card className="mb-8">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{t("dataset.apiExplorer.title")}</CardTitle>
        <p className="text-sm text-[var(--color-foreground-secondary)]">
          {t("dataset.apiExplorer.description")}
        </p>
        <div className="flex flex-wrap items-center gap-2 pt-2">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={tab === "rest" ? "default" : "secondary"}
              onClick={() => onTabChange("rest")}
            >
              {t("dataset.apiExplorer.tabRest")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={tab === "openapi" ? "default" : "secondary"}
              onClick={() => onTabChange("openapi")}
            >
              {t("dataset.apiExplorer.tabOpenApi")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={tab === "odata" ? "default" : "secondary"}
              onClick={() => onTabChange("odata")}
            >
              {t("dataset.apiExplorer.tabOData")}
            </Button>
          </div>
          <Button asChild size="sm" variant="secondary">
            <Link href={`/developer/explorer?dataset=${datasetId}`}>
              {t("dataset.apiExplorer.openDeveloperConsole")}
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {tab === "rest" ? (
          <>
            <div className="space-y-2">
              <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
                {t("dataset.apiExplorer.dataEndpoint")}
              </p>
              <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                {curlData}
              </pre>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => void onCopy("curl", curlData)}
              >
                {copied === "curl" ? t("dataset.embedCopied") : t("dataset.embedCopy")}
              </Button>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
                {t("dataset.apiExplorer.powershell")}
              </p>
              <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                {powershellData}
              </pre>
            </div>
          </>
        ) : null}

        {tab === "openapi" ? (
          <>
            {loading ? (
              <p className="text-sm text-[var(--color-foreground-secondary)]">
                {t("dataset.apiExplorer.loading")}
              </p>
            ) : null}
            {loadError ? (
              <p className="text-sm text-[var(--color-danger)]" role="alert">
                {loadError}
              </p>
            ) : null}
            {spec ? (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="font-medium">{spec.info?.title ?? slug}</span>
                  {spec.info?.version ? ` · v${spec.info.version}` : null}
                </p>
                <p className="text-[var(--color-foreground-secondary)]">
                  {t("dataset.apiExplorer.pathCount", { count: pathCount })}
                </p>
                <pre className="max-h-48 overflow-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                  {JSON.stringify(spec, null, 2)}
                </pre>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => void onCopy("openapi", curlOpenApi)}
                >
                  {copied === "openapi" ? t("dataset.embedCopied") : t("dataset.apiExplorer.fetchSpec")}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}

        {tab === "odata" ? (
          <>
            {loading ? (
              <p className="text-sm text-[var(--color-foreground-secondary)]">
                {t("dataset.apiExplorer.loadingOData")}
              </p>
            ) : null}
            {loadError ? (
              <p className="text-sm text-[var(--color-danger)]" role="alert">
                {loadError}
              </p>
            ) : null}
            {odata ? (
              <div className="space-y-3 text-sm">
                <p className="text-[var(--color-foreground-secondary)]">
                  {t("dataset.apiExplorer.odataVersion", { version: odata.odata_version ?? "4.0" })}
                </p>
                <div className="space-y-2">
                  <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
                    {t("dataset.apiExplorer.odataServiceRoot")}
                  </p>
                  <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                    {odata.service_root}
                  </pre>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
                    {t("dataset.apiExplorer.odataExample")}
                  </p>
                  <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                    {odataExample}
                  </pre>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => void onCopy("odata", odataExample)}
                  >
                    {copied === "odata" ? t("dataset.embedCopied") : t("dataset.embedCopy")}
                  </Button>
                </div>
                {odata.metadata_url ? (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
                      {t("dataset.apiExplorer.odataMetadata")}
                    </p>
                    <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                      {odata.metadata_url}
                    </pre>
                  </div>
                ) : null}
                <div className="space-y-2">
                  <p className="text-xs font-medium text-[var(--color-foreground-muted)]">
                    {t("dataset.apiExplorer.odataPowerQuery")}
                  </p>
                  <pre className="overflow-x-auto rounded-lg bg-[var(--color-surface-muted)] p-3 text-xs">
                    {powerQueryM}
                  </pre>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => void onCopy("powerquery", powerQueryM)}
                  >
                    {copied === "powerquery" ? t("dataset.embedCopied") : t("dataset.embedCopy")}
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
