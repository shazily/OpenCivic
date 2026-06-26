"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { syncConnectorClient, testConnectorClient } from "@/lib/api/admin-client";

export function ConnectorRowActions({ connectorId }: { connectorId: string }) {
  const { t } = useTranslation();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function runTest() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await testConnectorClient(connectorId);
      setMessage(
        result.data.message ||
          (result.data.ok ? t("admin.connectors.testOk") : t("admin.connectors.testFailed")),
      );
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : t("admin.connectors.testFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function runSync() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await syncConnectorClient(connectorId);
      setMessage(t("admin.connectors.syncQueued", { jobId: result.data.job_id }));
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : t("admin.connectors.syncFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void runTest()}>
        {t("admin.connectors.test")}
      </Button>
      <Button type="button" size="sm" variant="default" disabled={busy} onClick={() => void runSync()}>
        {t("admin.connectors.triggerSync")}
      </Button>
      {message ? <span className="text-xs text-[var(--color-foreground-muted)]">{message}</span> : null}
      {error ? (
        <span className="text-xs text-[var(--color-danger)]" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
