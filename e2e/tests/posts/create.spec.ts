import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Create Post", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "free");
  });

  test("navigates to new post page", async ({ page }) => {
    await page.goto("/posts/new");
    await expect(page.getByRole("heading")).toContainText(/new post/i);
  });

  test("shows platform selection chips", async ({ page }) => {
    await page.goto("/posts/new");
    await expect(page.getByText("youtube", { exact: false })).toBeVisible();
    await expect(page.getByText("linkedin", { exact: false })).toBeVisible();
    await expect(page.getByText("instagram", { exact: false })).toBeVisible();
  });

  test("can fill post form and select platforms", async ({ page }) => {
    await page.goto("/posts/new");

    await page.locator("textarea").fill("E2E test post content");
    // Select YouTube platform
    await page.locator("button", { hasText: /youtube/i }).click();
    // Select LinkedIn
    await page.locator("button", { hasText: /linkedin/i }).click();

    // Publish button should be enabled
    const submitBtn = page.getByRole("button", { name: /publish/i });
    await expect(submitBtn).toBeEnabled();
  });

  test("shows schedule mode when selected", async ({ page }) => {
    await page.goto("/posts/new");
    await page.locator("button", { hasText: /schedule/i }).click();
    await expect(page.locator("input[type=datetime-local]")).toBeVisible();
  });

  test("publish button disabled without platform selection", async ({ page }) => {
    await page.goto("/posts/new");
    await page.locator("textarea").fill("Some content");
    const submitBtn = page.getByRole("button", { name: /publish/i });
    await expect(submitBtn).toBeDisabled();
  });
});
