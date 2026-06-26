import { notFound } from "next/navigation";

import { DatasetApiExplorer } from "@/components/dataset-api-explorer";
import { DatasetChat } from "@/components/dataset-chat";
import { DatasetDetailHeader } from "@/components/dataset-detail-header";
import { DatasetEmbedPanel } from "@/components/dataset-embed-panel";
import { DatasetPreviewSection } from "@/components/dataset-preview-section";
import { DatasetFeedback } from "@/components/dataset-feedback";
import { GeoMapPreview } from "@/components/geo-map-preview";
import { PublicHeader } from "@/components/public-header";
import { SubmitForReview } from "@/components/submit-for-review";
import { MetadataEditor } from "@/components/metadata-editor";
import { detectGeoColumns } from "@/lib/geo/detect-geo";
import {
  getPublicDatasetConnectorServer,
  getPublicDatasetDataServer,
  getPublicDatasetServer,
  getPublicDatasetStatsServer,
  getPublicDatasetTrendServer,
  getPublicLineageServer,
} from "@/lib/api/server";
import { LineageGraph } from "@/components/lineage-graph";

export const dynamic = "force-dynamic";
export const revalidate = 60;

interface PageProps {
  params: { id: string };
}

export default async function DatasetDetailPage({ params }: PageProps) {
  let dataset;
  let rows: Record<string, unknown>[] = [];
  let dataError: string | null = null;

  let lineageNodes: Awaited<ReturnType<typeof getPublicLineageServer>>["data"]["nodes"] = [];
  let lineageEdges: Awaited<ReturnType<typeof getPublicLineageServer>>["data"]["edges"] = [];
  let stats: Awaited<ReturnType<typeof getPublicDatasetStatsServer>>["data"] | null = null;
  let trend: Awaited<ReturnType<typeof getPublicDatasetTrendServer>>["data"] = [];
  let connector: Awaited<ReturnType<typeof getPublicDatasetConnectorServer>>["data"] = null;

  try {
    const detail = await getPublicDatasetServer(params.id);
    dataset = detail.data;
  } catch {
    notFound();
  }

  if (!dataset) {
    notFound();
  }

  try {
    const data = await getPublicDatasetDataServer(params.id);
    rows = data.data;
  } catch (error) {
    dataError = error instanceof Error ? error.message : "No preview available";
  }

  try {
    const lineage = await getPublicLineageServer(params.id);
    lineageNodes = lineage.data.nodes;
    lineageEdges = lineage.data.edges;
  } catch {
    lineageNodes = [];
    lineageEdges = [];
  }

  if (dataset.status === "published") {
    try {
      const summary = await getPublicDatasetStatsServer(params.id);
      stats = summary.data;
    } catch {
      stats = null;
    }
    try {
      const trendResponse = await getPublicDatasetTrendServer(params.id);
      trend = trendResponse.data;
    } catch {
      trend = [];
    }
    try {
      const connectorResponse = await getPublicDatasetConnectorServer(params.id);
      connector = connectorResponse.data;
    } catch {
      connector = null;
    }
  }

  const columns =
    dataset.schema_snapshot?.columns?.map((column) => column.name) ||
    (rows[0] ? Object.keys(rows[0]) : []);

  const geoColumns = detectGeoColumns(columns);

  return (
    <>
      <PublicHeader />
      <main id="main-content" className="mx-auto max-w-6xl px-6 py-8">
        <DatasetDetailHeader
          dataset={dataset}
          stats={stats}
          trend={trend}
          connector={connector}
        />

        {dataset.status === "published" ? (
          <>
            <DatasetEmbedPanel datasetId={dataset.id} title={dataset.title} />
            <DatasetApiExplorer datasetId={dataset.id} slug={dataset.slug} />
          </>
        ) : null}

        <div className="mb-8 space-y-8">
        <MetadataEditor dataset={dataset} />

        <DatasetFeedback datasetId={dataset.id} published={dataset.status === "published"} />

        <DatasetChat
          datasetId={dataset.id}
          published={dataset.status === "published"}
          hasData={!dataError && rows.length > 0}
        />

        <SubmitForReview datasetId={dataset.id} status={dataset.status} />

        {geoColumns && rows.length > 0 ? (
          <GeoMapPreview rows={rows} geoColumns={geoColumns} />
        ) : null}

        <div className="mb-8 mt-8">
          <LineageGraph nodes={lineageNodes} edges={lineageEdges} />
        </div>

        <DatasetPreviewSection columns={columns} rows={rows} dataError={dataError} />
        </div>
      </main>
    </>
  );
}
