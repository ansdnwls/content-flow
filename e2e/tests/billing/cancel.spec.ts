import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";

test.describe("Billing Management", () => {
  test("shows payment management section", async ({ page }) => {
    await loginAs(page, "free");
    await page.goto("/billing");
    await expect(page.getByText(/manage payment/i)).toBeVisible();
  });

  test("has stripe portal button", async ({ page }) => {
    await loginAs(page, "free");
    await page.goto("/billing");
    const portalBtn = page.getByRole("button", { name: /stripe portal/i });
    await expect(portalBtn).toBeVisible();
  });
});
