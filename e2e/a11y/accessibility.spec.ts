import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { loginAs } from "../helpers/auth-helper";

const PAGES_TO_TEST = [
  { name: "login", path: "/login", auth: false },
  { name: "signup", path: "/signup", auth: false },
  { name: "dashboard", path: "/", auth: true },
  { name: "posts", path: "/posts", auth: true },
  { name: "posts-new", path: "/posts/new", auth: true },
  { name: "billing", path: "/billing", auth: true },
  { name: "settings", path: "/settings", auth: true },
];

test.describe("Accessibility", () => {
  for (const pg of PAGES_TO_TEST) {
    test(`${pg.name} has no critical a11y violations`, async ({ page }) => {
      if (pg.auth) {
        await loginAs(page, "free");
      }
      await page.goto(pg.path);
      await page.waitForLoadState("networkidle");

      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();

      const critical = results.violations.filter(
        (v) => v.impact === "critical" || v.impact === "serious",
      );

      expect(critical).toEqual([]);
    });
  }
});
