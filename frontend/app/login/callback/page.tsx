"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { setSession, staffDestinationForRole, type StaffRole } from "@/lib/auth/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

function OidcCallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    if (!code || !state) {
      setError("Missing authorization code from identity provider.");
      return;
    }

    const redirectUri = `${window.location.origin}/login/callback`;
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/oidc/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ code, state, redirect_uri: redirectUri }),
        });
        if (!response.ok) {
          throw new Error(`Sign-in failed (${response.status})`);
        }
        const body = (await response.json()) as {
          data: { access_token: string; staff_role?: StaffRole; roles?: string[] };
        };
        const role = (body.data.staff_role ?? "publisher") as StaffRole;
        setSession(body.data.access_token, role);
        router.replace(staffDestinationForRole(role));
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Sign-in failed");
      }
    })();
  }, [router, searchParams]);

  if (error) {
    return (
      <p className="p-8 text-center text-sm text-[var(--color-danger)]" role="alert">
        {error}
      </p>
    );
  }

  return <p className="p-8 text-center text-sm">Completing sign-in…</p>;
}

export default function OidcCallbackPage() {
  return (
    <Suspense fallback={<p className="p-8 text-center text-sm">Completing sign-in…</p>}>
      <OidcCallbackInner />
    </Suspense>
  );
}
