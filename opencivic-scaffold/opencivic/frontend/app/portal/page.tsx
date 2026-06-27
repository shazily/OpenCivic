import { Suspense } from "react";

// SSR — this page is server-rendered so search engines index every dataset
export const dynamic = "force-static";
export const revalidate = 60; // Revalidate every 60 seconds

export default function PortalPage() {
  return (
    <main>
      <a href="#main-content" className="skip-to-content">Skip to content</a>
      <div id="main-content">
        <Suspense fallback={<div>Loading...</div>}>
          <PortalContent />
        </Suspense>
      </div>
    </main>
  );
}

function PortalContent() {
  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "2rem" }}>
      <h1 style={{ fontSize: "2rem", fontWeight: 700, marginBottom: "1rem" }}>
        Open Data Portal
      </h1>
      <p style={{ color: "var(--color-foreground-secondary)", marginBottom: "2rem" }}>
        Discover, explore, and download open datasets. Use our API to integrate data directly into your applications.
      </p>
      {/* Search bar — Cmd+K triggers command palette */}
      <div style={{
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius)",
        padding: "0.75rem 1rem",
        background: "var(--color-background-secondary)",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
        color: "var(--color-foreground-muted)",
      }}>
        <span>🔍</span>
        <span>Search datasets... (Cmd+K)</span>
      </div>
    </div>
  );
}
