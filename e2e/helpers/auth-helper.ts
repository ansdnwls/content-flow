import { type Page, expect } from "@playwright/test";
import { TEST_USERS, type TestUserPlan } from "../fixtures/test-users";

/**
 * Log in as a test user via the login form.
 */
export async function loginAs(page: Page, plan: TestUserPlan = "free") {
  const user = TEST_USERS[plan];
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(user.email);
  await page.getByLabel(/password/i).fill(user.password);
  await page.getByRole("button", { name: /sign in/i }).click();
  // Wait for redirect to dashboard
  await page.waitForURL("**/");
  await expect(page.locator("aside")).toBeVisible();
}

/**
 * Sign up a new user with a unique email.
 */
export async function signUp(page: Page, suffix?: string) {
  const email = `test_${suffix ?? Date.now()}@contentflow.dev`;
  await page.goto("/signup");
  await page.getByLabel(/name/i).fill("E2E Tester");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill("TestPass123!");
  await page.getByRole("button", { name: /create/i }).click();
  return email;
}
