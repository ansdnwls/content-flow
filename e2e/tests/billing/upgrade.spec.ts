import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";
import { mockStripeCheckout } from "../../mocks/mock-oauth";

test.describe("Billing Upgrade", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "free");
  });

  test("shows billing page with plans", async ({ page }) => {
    await page.goto("/billing");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByText("Free")).toBeVisible();
    await expect(page.getByText("Build")).toBeVisible();
    await expect(page.getByText("Scale")).toBeVisible();
  });

  test("shows current plan indicator", async ({ page }) => {
    await page.goto("/billing");
    const currentBtn = page.getByRole("button", { name: /current plan/i });
    await expect(currentBtn).toBeVisible();
    await expect(currentBtn).toBeDisabled();
  });

  test("shows plan features", async ({ page }) => {
    await page.goto("/billing");
    await expect(page.getByText(/posts\/month/i).first()).toBeVisible();
  });

  test("shows usage progress bar", async ({ page }) => {
    await page.goto("/billing");
    const progressBar = page.locator(".bg-gradient-accent").first();
    await expect(progressBar).toBeVisible();
  });

  test("shows invoices section", async ({ page }) => {
    await page.goto("/billing");
    await expect(page.getByText(/invoice/i)).toBeVisible();
  });

  test("can initiate upgrade flow", async ({ page }) => {
    await mockStripeCheckout(page);
    await page.goto("/billing");
    const upgradeBtn = page.getByRole("button", { name: /upgrade to build/i });
    await expect(upgradeBtn).toBeVisible();
  });
});
