import { expect, test } from "@playwright/test";

test.describe("Pilot auth UI", () => {
  test.skip(
    process.env.OPENCIVIC_PILOT_AUTH !== "true",
    "Set OPENCIVIC_PILOT_AUTH=true when Keycloak pilot overlay is running",
  );

  test("login shows SSO without dev role radios", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: /Sign in with SSO/i })).toBeVisible();
    await expect(page.getByRole("radio", { name: /Data Publisher/i })).toHaveCount(0);
  });

  test("SSO button navigates to Keycloak authorization URL", async ({ page }) => {
    await page.goto("/login");
    await Promise.all([
      page.waitForURL(/realms\/dev\/protocol\/openid-connect\/auth/),
      page.getByRole("button", { name: /Sign in with SSO/i }).click(),
    ]);
  });

  test("publisher signs in via Keycloak and reaches dashboard", async ({ page }) => {
    test.setTimeout(60_000);

    await page.goto("/login");
    await page.getByRole("button", { name: /Sign in with SSO/i }).click();
    await page.waitForURL(/realms\/dev/);

    await page.locator("#username").fill("publisher");
    await page.locator("#password").fill("publisher");
    await page.locator("#kc-login").click();

    await expect(page).toHaveURL(/\/portal\/dashboard/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /Publisher dashboard/i })).toBeVisible();
  });
});
