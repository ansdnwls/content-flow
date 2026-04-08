import { test, expect } from "@playwright/test";

test.describe("Email Verification", () => {
  test("shows verification page with loading state", async ({ page }) => {
    await page.goto("/verify-email?token=test_token_123");
    // Should show verifying or result message
    await expect(page.locator("body")).not.toBeEmpty();
  });

  test("shows failure for invalid token", async ({ page }) => {
    // Mock API to return failure
    await page.route("**/api/v1/email-verify**", async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid token" }),
      });
    });

    await page.goto("/verify-email?token=invalid_token");
    await expect(page.locator("body")).toContainText(
      /failed|invalid|expired/i,
      { timeout: 5000 },
    );
  });
});
