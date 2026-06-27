import { DeveloperDatasetExplorer } from "@/components/developer-dataset-explorer";

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: { dataset?: string };
}

export default function OpenApiExplorerPage({ searchParams }: PageProps) {
  return <DeveloperDatasetExplorer datasetId={searchParams.dataset} />;
}
