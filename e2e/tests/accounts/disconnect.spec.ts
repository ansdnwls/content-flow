import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Disconnect Account", () => {
  test("shows disconnect button on connected accounts", async ({ page }) => {
    await loginAs(page, "free");
    await page.goto("/accounts");
    const disconnectBtns = page.locator("button", { hasText: /disconnect/i });
    await expect(disconnectBtns.first()).toBeVisible();
  });

  test("shows token expiry warning for unhealthy accounts", async ({ page }) => {
    await loginAs(page, "free");
    await page.goto("/accounts");
    // Demo data has an unhealthy x_twitter account
    await expect(page.locator("[class*=danger]").first()).toBeVisible();
  });
});
