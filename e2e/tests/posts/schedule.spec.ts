import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Schedule Post", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "free");
  });

  test("can switch between publish now and schedule modes", async ({ page }) => {
    await page.goto("/posts/new");

    // Default is "now" mode
    const scheduleBtn = page.locator("button", { hasText: /schedule/i }).first();
    await scheduleBtn.click();

    // Should show datetime picker
    await expect(page.locator("input[type=datetime-local]")).toBeVisible();

    // Switch back to "now"
    const nowBtn = page.locator("button", { hasText: /publish now/i });
    await nowBtn.click();
    await expect(page.locator("input[type=datetime-local]")).not.toBeVisible();
  });

  test("schedule button text changes when schedule mode active", async ({ page }) => {
    await page.goto("/posts/new");

    // Select a platform first
    await page.locator("button", { hasText: /youtube/i }).click();
    await page.locator("textarea").fill("Scheduled post");

    // Switch to schedule mode
    await page.locator("button", { hasText: /schedule/i }).first().click();

    // Submit button should say "Schedule Post"
    const submitBtn = page.getByRole("button", { name: /schedule post/i });
    await expect(submitBtn).toBeVisible();
  });
});
