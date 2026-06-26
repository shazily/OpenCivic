import { expect, test } from "@playwright/test";

import { expectPathname } from "./helpers";

test.describe("OIDC callback flow", () => {
  test("token exchange redirects publisher to dashboard", async ({ page }) => {
    const apiBase = process.env.OPENCIVIC_API_URL ?? "http://127.0.0.1:8100/api/v1";

    await page.route(`${apiBase}/auth/oidc/callback`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            access_token: "e2e-oidc-access-token",
            token_type: "Bearer",
            expires_in: 900,
            staff_role: "publisher",
            roles: ["data_publisher"],
          },
          meta: {},
          errors: [],
        }),
      });
    });

    await page.goto("/login/callback?code=e2e-code&state=e2e-state");
    await expectPathname(page, "/portal/dashboard");
    await expect(page.getByRole("heading", { name: "Publisher dashboard" })).toBeVisible({
      timeout: 15000,
    });
  });
});
