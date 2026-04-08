import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Language Switching", () => {
  test("can switch to Korean", async ({ page }) => {
    await loginAs(page, "free");
    // Click language switcher
    await page.locator("button", { hasText: /globe|language/i }).first().click();
    await page.getByText("한국어").click();
    await expect(page).toHaveURL(/\/ko\//);
    // Nav should show Korean labels
    await expect(page.locator("nav")).toContainText("포스트");
  });

  test("can switch to Japanese", async ({ page }) => {
    await loginAs(page, "free");
    await page.locator("button", { hasText: /globe|language/i }).first().click();
    await page.getByText("日本語").click();
    await expect(page).toHaveURL(/\/ja\//);
    await expect(page.locator("nav")).toContainText("投稿");
  });

  test("can switch to English", async ({ page }) => {
    await loginAs(page, "free");
    // Navigate to Korean first
    await page.goto("/ko/");
    await page.locator("button", { hasText: /globe|language/i }).first().click();
    await page.getByText("English").click();
    await expect(page).toHaveURL(/\/en\//);
    await expect(page.locator("nav")).toContainText("Posts");
  });

  test("login page respects locale", async ({ page }) => {
    await page.goto("/ko/login");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("다시 오셨군요");
  });

  test("signup page respects locale", async ({ page }) => {
    await page.goto("/ja/signup");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("アカウントを作成");
  });
});
