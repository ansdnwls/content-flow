import { test, expect } from "@playwright/test";
import { loginAs } from "../../helpers/auth-helper";
import { mockVideoGeneration } from "../../mocks/mock-oauth";

test.describe("Video Auto-Publish", () => {
  test("can generate video with auto-publish enabled", async ({ page }) => {
    await loginAs(page, "free");
    await mockVideoGeneration(page);

    await page.goto("/videos/new");
    await page.locator("input[type=text]").fill("Auto-publish test video");
    await page.locator("select").first().selectOption("legal");

    // Enable auto-publish
    const toggle = page.locator("button[aria-pressed]");
    await toggle.click();

    // Submit
    await page.getByRole("button", { name: /generate/i }).click();

    // Should redirect to videos list on success
    await page.waitForURL("**/videos", { timeout: 10000 });
  });
});
