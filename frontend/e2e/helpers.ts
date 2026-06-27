import { expect, type Page } from "@playwright/test";

/** Assert pathname exactly — avoids false positives from `next=` query params. */
export async function expectPathname(page: Page, pathname: string): Promise<void> {
  await expect(page).toHaveURL((url) => new URL(url).pathname === pathname);
}
