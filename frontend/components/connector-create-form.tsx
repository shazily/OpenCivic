"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createConnectorClient } from "@/lib/api/admin-client";

type ConnectorType = "rest_api" | "postgres" | "mysql" | "mssql" | "oracle" | "sqlite" | "minio";

export function ConnectorCreateForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [type, setType] = useState<ConnectorType>("rest_api");
  const [url, setUrl] = useState("https://jsonplaceholder.typicode.com/users");
  const [host, setHost] = useState("postgres");
  const [database, setDatabase] = useState("opencivic");
  const [user, setUser] = useState("opencivic");
  const [password, setPassword] = useState("");
  const [table, setTable] = useState("datasets");
  const [sqlitePath, setSqlitePath] = useState("/data/sample.db");
  const [bucket, setBucket] = useState("opencivic");
  const [prefix, setPrefix] = useState("imports/");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function buildConfig(): Record<string, unknown> {
    if (type === "rest_api") {
      return { url: url.trim(), auth_type: "none", content_type: "json" };
    }
    if (type === "minio") {
      return {
        endpoint_url: "http://minio:9000",
        access_key: "minioadmin",
        secret_key: "minioadmin",
        bucket: bucket.trim(),
        prefix: prefix.trim(),
      };
    }
    if (type === "sqlite") {
      return {
        path: sqlitePath.trim(),
        table: table.trim(),
      };
    }
    return {
      host: host.trim(),
      database: database.trim(),
      user: user.trim(),
      password,
      table: table.trim(),
    };
  }

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      await createConnectorClient({
        name: name.trim(),
        type,
        config: buildConfig(),
      });
      setName("");
      router.refresh();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-[var(--color-border)] p-4">
      <h2 className="mb-3 text-lg font-semibold">Add connector</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">
          <span>Name</span>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Production feed" />
        </label>
        <label className="grid gap-1 text-sm">
          <span>Type</span>
          <select
            className="h-10 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
            value={type}
            onChange={(e) => setType(e.target.value as ConnectorType)}
          >
            <option value="rest_api">REST API</option>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL</option>
            <option value="mssql">Microsoft SQL Server</option>
            <option value="oracle">Oracle Database</option>
            <option value="sqlite">SQLite</option>
            <option value="minio">Minio / S3</option>
          </select>
        </label>
        {type === "rest_api" ? (
          <label className="grid gap-1 text-sm sm:col-span-2">
            <span>URL</span>
            <Input value={url} onChange={(e) => setUrl(e.target.value)} />
          </label>
        ) : null}
        {type === "postgres" || type === "mysql" || type === "mssql" || type === "oracle" ? (
          <>
            <label className="grid gap-1 text-sm">
              <span>Host</span>
              <Input value={host} onChange={(e) => setHost(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm">
              <span>{type === "oracle" ? "Service name" : "Database"}</span>
              <Input value={database} onChange={(e) => setDatabase(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm">
              <span>User</span>
              <Input value={user} onChange={(e) => setUser(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm">
              <span>Password</span>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm sm:col-span-2">
              <span>Table</span>
              <Input value={table} onChange={(e) => setTable(e.target.value)} />
            </label>
          </>
        ) : null}
        {type === "sqlite" ? (
          <>
            <label className="grid gap-1 text-sm sm:col-span-2">
              <span>Database file path</span>
              <Input value={sqlitePath} onChange={(e) => setSqlitePath(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm sm:col-span-2">
              <span>Table</span>
              <Input value={table} onChange={(e) => setTable(e.target.value)} />
            </label>
          </>
        ) : null}
        {type === "minio" ? (
          <>
            <label className="grid gap-1 text-sm">
              <span>Bucket</span>
              <Input value={bucket} onChange={(e) => setBucket(e.target.value)} />
            </label>
            <label className="grid gap-1 text-sm">
              <span>Prefix</span>
              <Input value={prefix} onChange={(e) => setPrefix(e.target.value)} />
            </label>
          </>
        ) : null}
      </div>
      {error ? (
        <p className="mt-2 text-sm text-[var(--color-danger)]" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="button" className="mt-3" disabled={busy || !name.trim()} onClick={() => void handleCreate()}>
        {busy ? "Creating…" : "Create connector"}
      </Button>
    </section>
  );
}
