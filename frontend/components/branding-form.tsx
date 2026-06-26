"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getAdminBranding, patchAdminBranding, type BrandingData } from "@/lib/api/admin-client";

export function BrandingForm() {
  const { t } = useTranslation();
  const [data, setData] = useState<BrandingData | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#2563eb");
  const [primaryHover, setPrimaryHover] = useState("#1d4ed8");
  const [accentColor, setAccentColor] = useState("#f59e0b");
  const [logoUrl, setLogoUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const response = await getAdminBranding();
        setData(response.data);
        setDisplayName(response.data.display_name);
        setPrimaryColor(response.data.branding.primary_color ?? "#2563eb");
        setPrimaryHover(response.data.branding.primary_hover_color ?? "#1d4ed8");
        setAccentColor(response.data.branding.accent_color ?? "#f59e0b");
        setLogoUrl(response.data.branding.logo_url ?? "");
      } catch (err) {
        setError(err instanceof Error ? err.message : t("admin.branding.loadFailed"));
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--color-primary", primaryColor);
    root.style.setProperty("--color-primary-hover", primaryHover);
    root.style.setProperty("--color-accent", accentColor);
  }, [primaryColor, primaryHover, accentColor]);

  const onSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const response = await patchAdminBranding({
        display_name: displayName,
        primary_color: primaryColor,
        primary_hover_color: primaryHover,
        accent_color: accentColor,
        logo_url: logoUrl || undefined,
      });
      setData(response.data);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("admin.branding.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-sm text-[var(--color-foreground-muted)]">{t("admin.branding.loading")}</p>;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.branding.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="display-name" className="text-sm font-medium">
              {t("admin.branding.displayName")}
            </label>
            <Input id="display-name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <label htmlFor="primary-color" className="text-sm font-medium">
              {t("admin.branding.primaryColor")}
            </label>
            <Input
              id="primary-color"
              type="color"
              value={primaryColor}
              onChange={(e) => setPrimaryColor(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="primary-hover" className="text-sm font-medium">
              {t("admin.branding.primaryHover")}
            </label>
            <Input
              id="primary-hover"
              type="color"
              value={primaryHover}
              onChange={(e) => setPrimaryHover(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="accent-color" className="text-sm font-medium">
              {t("admin.branding.accentColor")}
            </label>
            <Input
              id="accent-color"
              type="color"
              value={accentColor}
              onChange={(e) => setAccentColor(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="logo-url" className="text-sm font-medium">
              {t("admin.branding.logoUrl")}
            </label>
            <Input
              id="logo-url"
              type="url"
              placeholder="https://example.org/logo.svg"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
            />
          </div>
          {error ? (
            <p className="text-sm text-[var(--color-danger)]" role="alert">
              {error}
            </p>
          ) : null}
          {saved ? (
            <p className="text-sm text-[var(--color-success)]">{t("admin.branding.saved")}</p>
          ) : null}
          <Button type="button" disabled={saving} onClick={() => void onSave()}>
            {saving ? t("admin.branding.saving") : t("admin.branding.save")}
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.branding.preview")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4" data-branding-preview>
          <div className="flex items-center gap-3">
            {logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logoUrl} alt="" className="h-10 w-10 object-contain" />
            ) : null}
            <span className="text-lg font-semibold">{displayName || data?.display_name}</span>
          </div>
          <Button type="button">{t("admin.branding.sampleButton")}</Button>
          <p className="text-sm text-[var(--color-foreground-secondary)]">
            {t("admin.branding.previewHint")}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
