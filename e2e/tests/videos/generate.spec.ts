import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Generate Video", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "free");
  });

  test("shows video generation form", async ({ page }) => {
    await page.goto("/videos/new");
    await expect(page.getByRole("heading")).toContainText(/generate/i);
    await expect(page.locator("input[type=text]")).toBeVisible();
    await expect(page.locator("select").first()).toBeVisible();
  });

  test("can fill video form", async ({ page }) => {
    await page.goto("/videos/new");
    await page.locator("input[type=text]").fill("How DUI laws work");
    await page.locator("select").first().selectOption("legal");

    const submitBtn = page.getByRole("button", { name: /generate/i });
    await expect(submitBtn).toBeEnabled();
  });

  test("shows template selection", async ({ page }) => {
    await page.goto("/videos/new");
    await expect(page.getByText("Cinematic")).toBeVisible();
    await expect(page.getByText("Minimal")).toBeVisible();
    await expect(page.getByText("Dynamic")).toBeVisible();
  });

  test("has auto-publish toggle", async ({ page }) => {
    await page.goto("/videos/new");
    const toggle = page.locator("button[aria-pressed]");
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
  });
});
