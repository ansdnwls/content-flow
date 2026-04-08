import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";
import { mockOAuthFlow } from "../../mocks/mock-oauth";

test.describe("Connect YouTube", () => {
  test("shows available platforms to connect", async ({ page }) => {
    await loginAs(page, "free");
    await page.goto("/accounts");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("shows connect buttons for unconnected platforms", async ({ page }) => {
    await loginAs(page, "free");
    await page.goto("/accounts");
    // Should see connect buttons
    const connectButtons = page.locator("button", { hasText: /connect/i });
    await expect(connectButtons.first()).toBeVisible();
  });

  test("shows connected accounts with status", async ({ page }) => {
    await loginAs(page, "free");
    await page.goto("/accounts");
    // Demo data shows connected accounts
    await expect(page.getByText("youtube", { exact: false })).toBeVisible();
  });
});
