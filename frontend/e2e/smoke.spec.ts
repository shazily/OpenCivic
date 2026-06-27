import { expect, test } from "@playwright/test";

import { expectPathname } from "./helpers";

test.describe("OpenCivic UI smoke", () => {
  test("public catalog loads", async ({ page }) => {
    await page.goto("/portal");
    await expect(page.getByRole("heading", { name: "Open Data Catalog" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Staff sign-in" })).toBeVisible();
  });

  test("public home shows trust signals", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Open data you can trust/i })).toBeVisible();
    await expect(page.getByRole("link", { name: "Browse catalog" })).toBeVisible();
  });

  test("login page loads", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Staff sign-in" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();
  });

  test("admin requires sign-in", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login/);
  });

  test("admin overview after org_admin sign-in", async ({ page }) => {
    await page.goto("/login?role=admin&next=/admin");
    await page.getByRole("radio", { name: /Org Admin/i }).check();
    await page.getByRole("button", { name: "Continue" }).click();
    await expectPathname(page, "/admin");
    await expect(page.getByRole("heading", { name: "IT Admin overview" })).toBeVisible();
  });

  test("publisher dashboard after sign-in", async ({ page }) => {
    await page.goto("/login?role=publisher&next=/portal/dashboard");
    await page.getByRole("radio", { name: /Data Publisher/i }).check();
    await page.getByRole("button", { name: "Continue" }).click();
    await expectPathname(page, "/portal/dashboard");
    await expect(page.getByRole("heading", { name: "Publisher dashboard" })).toBeVisible();
  });

  test("steward review queue after sign-in", async ({ page }) => {
    await page.goto("/login?role=steward&next=/portal/review");
    await page.getByRole("radio", { name: /Data Steward/i }).check();
    await page.getByRole("button", { name: "Continue" }).click();
    await expectPathname(page, "/portal/review");
    await expect(page.getByRole("heading", { name: "Steward review queue" })).toBeVisible();
  });

  test("senior approval queue after org_admin sign-in", async ({ page }) => {
    await page.goto("/login?role=admin&next=/portal/approval");
    await page.getByRole("radio", { name: /Org Admin/i }).check();
    await page.getByRole("button", { name: "Continue" }).click();
    await expectPathname(page, "/portal/approval");
    await expect(page.getByRole("heading", { name: "Senior approval queue" })).toBeVisible();
  });

  test("developer console after developer sign-in", async ({ page }) => {
    await page.goto("/login?role=developer&next=/developer");
    await page.getByRole("radio", { name: /Developer/i }).check();
    await page.getByRole("button", { name: "Continue" }).click();
    await expectPathname(page, "/developer");
    await expect(page.getByRole("heading", { name: "Developer console" })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByRole("main").getByRole("link", { name: "API keys" })).toBeVisible();
  });

  test("developer api keys page after sign-in", async ({ page }) => {
    await page.goto("/login?role=developer&next=/developer/api-keys");
    await page.getByRole("radio", { name: /Developer/i }).check();
    await page.getByRole("button", { name: "Continue" }).click();
    await expectPathname(page, "/developer/api-keys");
    await expect(page.getByRole("heading", { name: "API keys" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create key" })).toBeVisible();
  });

  test("admin branding page after org_admin sign-in", async ({ page }) => {
    await page.goto("/login?role=admin&next=/admin/branding");
    await page.getByRole("radio", { name: /Org Admin/i }).check();
    await page.getByRole("button", { name: "Continue" }).click();
    await expectPathname(page, "/admin/branding");
    await expect(page.locator("[data-branding-preview]")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: /save branding|enregistrer|guardar marca/i })).toBeVisible();
  });
});
