import { PublicHeader } from "@/components/public-header";
import { PublicHomeHero } from "@/components/public-home-hero";
import { listPublicDatasetsServer } from "@/lib/api/server";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let publishedCount = 0;

  try {
    const response = await listPublicDatasetsServer({ pageSize: 1 });
    publishedCount = response.meta.total_count ?? response.data.length;
  } catch {
    publishedCount = 0;
  }

  return (
    <>
      <PublicHeader />
      <main id="main-content" className="mx-auto max-w-6xl px-6 py-10">
        <PublicHomeHero publishedCount={publishedCount} />
      </main>
    </>
  );
}
