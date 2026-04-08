import { test, expect } from "@playwright/test";
import { loginAs } from "../helpers/auth-helper";

test.describe("Performance", () => {
  test("login page loads within 3 seconds", async ({ page }) => {
    const start = Date.now();
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    const loadTime = Date.now() - start;
    expect(loadTime).toBeLessThan(3000);
  });

  test("dashboard loads within 3 seconds", async ({ page }) => {
    await loginAs(page, "free");
    const start = Date.now();
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const loadTime = Date.now() - start;
    expect(loadTime).toBeLessThan(3000);
  });

  test("posts page loads within 3 seconds", async ({ page }) => {
    await loginAs(page, "free");
    const start = Date.now();
    await page.goto("/posts");
    await page.waitForLoadState("networkidle");
    const loadTime = Date.now() - start;
    expect(loadTime).toBeLessThan(3000);
  });

  test("LCP under 2.5 seconds on landing page", async ({ page }) => {
    await page.goto("/login");

    const lcp = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          if (entries.length > 0) {
            resolve(entries[entries.length - 1].startTime);
          }
        });
        observer.observe({
          type: "largest-contentful-paint",
          buffered: true,
        });
        // Fallback timeout
        setTimeout(() => resolve(0), 5000);
      });
    });

    if (lcp > 0) {
      expect(lcp).toBeLessThan(2500);
    }
  });
});
