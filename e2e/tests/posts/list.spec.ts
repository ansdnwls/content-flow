import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Posts List", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "free");
  });

  test("displays posts page with title", async ({ page }) => {
    await page.goto("/posts");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("has search input", async ({ page }) => {
    await page.goto("/posts");
    await expect(page.getByPlaceholder(/search/i)).toBeVisible();
  });

  test("has status filter dropdown", async ({ page }) => {
    await page.goto("/posts");
    await expect(page.locator("select")).toBeVisible();
  });

  test("has new post button that navigates correctly", async ({ page }) => {
    await page.goto("/posts");
    const newPostLink = page.getByRole("link", { name: /new post/i });
    await expect(newPostLink).toBeVisible();
    await newPostLink.click();
    await expect(page).toHaveURL(/\/posts\/new/);
  });

  test("can filter by status", async ({ page }) => {
    await page.goto("/posts");
    await page.locator("select").selectOption("published");
    // Page should still be on posts
    await expect(page).toHaveURL(/\/posts/);
  });
});
