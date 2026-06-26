"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { setSession, type StaffRole } from "@/lib/auth/session";
import { LanguageSwitcher } from "@/components/language-switcher";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

const ROLE_IDS: StaffRole[] = ["publisher", "steward", "admin", "developer"];

interface AuthConfig {
  dev_auth_enabled: boolean;
  keycloak_enabled: boolean;
}

export function LoginForm() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/portal";
  const suggestedRole = (searchParams.get("role") as StaffRole | null) ?? "publisher";
  const [role, setRole] = useState<StaffRole>(suggestedRole);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/config`);
        if (!response.ok) {
          return;
        }
        const body = (await response.json()) as { data: AuthConfig };
        setAuthConfig(body.data);
      } catch {
        setAuthConfig({ dev_auth_enabled: true, keycloak_enabled: false });
      }
    })();
  }, []);

  const signIn = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/auth/dev-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ role }),
      });
      if (!response.ok) {
        throw new Error(`Sign-in failed (${response.status})`);
      }
      const body = (await response.json()) as {
        data: { access_token: string; roles: string[] };
      };
      setSession(body.data.access_token, role);
      router.push(next);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.signInFailed"));
    } finally {
      setLoading(false);
    }
  };

  const signInWithKeycloak = async () => {
    setLoading(true);
    setError(null);
    try {
      const redirectUri = `${window.location.origin}/login/callback`;
      const response = await fetch(
        `${API_BASE}/auth/oidc/login?redirect_uri=${encodeURIComponent(redirectUri)}`,
      );
      if (!response.ok) {
        throw new Error(`SSO sign-in failed (${response.status})`);
      }
      const body = (await response.json()) as {
        data: { authorization_url: string };
      };
      window.location.href = body.data.authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.ssoFailed"));
      setLoading(false);
    }
  };

  const showDevLogin = authConfig?.dev_auth_enabled !== false;
  const showKeycloak = authConfig?.keycloak_enabled === true;
  const keycloakOnly = showKeycloak && authConfig?.dev_auth_enabled === false;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[var(--color-background-secondary)] p-6">
      <div className="mb-4 w-full max-w-md flex justify-end">
        <LanguageSwitcher />
      </div>
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("login.title")}</CardTitle>
          <CardDescription>
            {showKeycloak ? t("login.descriptionSso") : t("login.descriptionDev")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {showKeycloak ? (
            <Button
              type="button"
              className="w-full"
              variant="secondary"
              disabled={loading}
              onClick={() => void signInWithKeycloak()}
            >
              {loading ? t("login.redirecting") : t("login.ssoButton")}
            </Button>
          ) : null}
          {showDevLogin && !keycloakOnly ? (
            <>
              {showKeycloak ? (
                <p className="text-center text-xs text-[var(--color-foreground-muted)]">
                  {t("login.orDevRole")}
                </p>
              ) : null}
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">{t("login.roleLegend")}</legend>
                {ROLE_IDS.map((item) => (
                  <label
                    key={item}
                    className="flex cursor-pointer items-start gap-3 rounded-md border border-[var(--color-border)] p-3 has-[:checked]:border-[var(--color-primary)] has-[:checked]:bg-[var(--color-background-secondary)]"
                  >
                    <input
                      type="radio"
                      name="role"
                      value={item}
                      checked={role === item}
                      onChange={() => setRole(item)}
                      className="mt-1"
                    />
                    <span>
                      <span className="block font-medium">{t(`login.roles.${item}.label`)}</span>
                      <span className="text-sm text-[var(--color-foreground-secondary)]">
                        {t(`login.roles.${item}.description`)}
                      </span>
                    </span>
                  </label>
                ))}
              </fieldset>
              <Button
                type="button"
                className="w-full"
                disabled={loading}
                onClick={() => void signIn()}
              >
                {loading ? t("login.signingIn") : t("login.continue")}
              </Button>
            </>
          ) : null}
          {error ? (
            <p className="text-sm text-[var(--color-danger)]" role="alert">
              {error}
            </p>
          ) : null}
          <p className="text-center text-sm text-[var(--color-foreground-muted)]">
            <Link href="/portal" className="underline hover:text-[var(--color-foreground)]">
              {t("login.backToCatalog")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
