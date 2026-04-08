import { test, expect } from "@playwright/test";

test.describe("Signup", () => {
  test("shows signup form with all fields", async ({ page }) => {
    await page.goto("/signup");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByLabel(/name/i)).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /create/i })).toBeVisible();
  });

  test("shows validation error for short password", async ({ page }) => {
    await page.goto("/signup");
    await page.getByLabel(/name/i).fill("Tester");
    await page.getByLabel(/email/i).fill("short@example.com");
    await page.getByLabel(/password/i).fill("123");
    await page.getByRole("button", { name: /create/i }).click();
    // HTML5 minLength validation prevents submission
    await expect(page).toHaveURL(/\/signup/);
  });

  test("navigates to login page from signup", async ({ page }) => {
    await page.goto("/signup");
    await page.getByRole("link", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
