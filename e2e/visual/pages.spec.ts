import { test, expect } from "@playwright/test";
import { loginAs } from "../helpers/auth-helper";

const PAGES = [
  { name: "login", path: "/login", auth: false },
  { name: "signup", path: "/signup", auth: false },
  { name: "dashboard", path: "/", auth: true },
  { name: "posts", path: "/posts", auth: true },
  { name: "posts-new", path: "/posts/new", auth: true },
  { name: "analytics", path: "/analytics", auth: true },
  { name: "billing", path: "/billing", auth: true },
  { name: "settings", path: "/settings", auth: true },
];

test.describe("Visual Regression", () => {
  for (const pg of PAGES) {
    test(`${pg.name} matches screenshot`, async ({ page }) => {
      if (pg.auth) {
        await loginAs(page, "free");
      }
      await page.goto(pg.path);
      await page.waitForLoadState("networkidle");
      // Allow animations to settle
      await page.waitForTimeout(500);
      await expect(page).toHaveScreenshot(`${pg.name}.png`, {
        maxDiffPixels: 200,
        fullPage: true,
      });
    });
  }
});
