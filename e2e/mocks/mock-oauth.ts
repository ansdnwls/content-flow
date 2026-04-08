import { type Page } from "@playwright/test";

/**
 * Intercept OAuth redirect and simulate a successful callback.
 * This prevents tests from hitting real OAuth providers.
 */
export async function mockOAuthFlow(
  page: Page,
  provider: string,
  opts?: { username?: string },
) {
  const username = opts?.username ?? `test_${provider}_user`;

  // Intercept any request going to OAuth authorize endpoints
  await page.route("**/oauth2/authorize**", async (route) => {
    const url = new URL(route.request().url());
    const state = url.searchParams.get("state") ?? "";
    const redirectUri =
      url.searchParams.get("redirect_uri") ?? "http://localhost:8000/oauth/callback";

    // Simulate OAuth provider redirecting back with a code
    const callbackUrl = `${redirectUri}?code=mock_code_${provider}&state=${state}`;
    await route.fulfill({
      status: 302,
      headers: { Location: callbackUrl },
    });
  });

  // Mock the token exchange on the backend side
  await page.route("**/api/v1/accounts/oauth/callback**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        platform: provider,
        username,
        connected: true,
      }),
    });
  });
}

/**
 * Mock Stripe Checkout session creation.
 */
export async function mockStripeCheckout(page: Page) {
  await page.route("**/api/v1/billing/checkout", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        checkout_url: "/billing?session_id=cs_test_mock_123&success=true",
      }),
    });
  });
}

/**
 * Mock yt-factory video generation.
 */
export async function mockVideoGeneration(page: Page) {
  await page.route("**/api/v1/videos", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "mock_video_001",
          status: "completed",
          topic: "Mock video",
          video_url: "https://example.com/mock-video.mp4",
        }),
      });
    } else {
      await route.continue();
    }
  });
}
