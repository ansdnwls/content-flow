import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Analytics Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "free");
  });

  test("displays analytics page with title", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("shows period filter buttons", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page.getByRole("button", { name: /7/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /30/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /90/ })).toBeVisible();
  });

  test("can switch period filter", async ({ page }) => {
    await page.goto("/analytics");
    await page.getByRole("button", { name: /30/ }).click();
    // Button should be active (has accent styling)
    const btn30 = page.getByRole("button", { name: /30/ });
    await expect(btn30).toHaveClass(/accent/);
  });

  test("shows chart sections", async ({ page }) => {
    await page.goto("/analytics");
    // Should have chart containers
    const glassCards = page.locator(".glass-card");
    await expect(glassCards).toHaveCount(4, { timeout: 5000 });
  });

  test("shows top posts section", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page.getByText(/top post/i)).toBeVisible();
  });
});
