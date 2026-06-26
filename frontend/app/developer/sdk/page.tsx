import { getDeveloperSdkServer } from "@/lib/api/developer";

export const dynamic = "force-dynamic";

export default async function SdkPage() {
  const response = await getDeveloperSdkServer();

  return (
    <main style={{ padding: "2rem" }}>
      <h1 style={{ fontSize: "1.75rem", fontWeight: 700, marginBottom: "1rem" }}>SDK snippets</h1>
      {(["python", "javascript", "curl"] as const).map((lang) => (
        <section key={lang} style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ fontWeight: 600, textTransform: "capitalize" }}>{lang}</h2>
          <pre
            style={{
              padding: "1rem",
              overflow: "auto",
              background: "var(--color-background-secondary)",
              borderRadius: "var(--radius)",
            }}
          >
            {response.data[lang]}
          </pre>
        </section>
      ))}
    </main>
  );
}
