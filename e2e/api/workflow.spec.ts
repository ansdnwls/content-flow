import { test, expect } from "@playwright/test";
import { TEST_USERS } from "../fixtures/test-users";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

function apiHeaders(plan: "free" | "build" | "scale" = "free") {
  return {
    "Content-Type": "application/json",
    "X-API-Key": TEST_USERS[plan].apiKey,
  };
}

test.describe("API E2E Workflow", () => {
  test("health check returns ok", async ({ request }) => {
    const res = await request.get(`${API_URL}/health`);
    expect(res.ok()).toBe(true);
  });

  test("post creation returns success", async ({ request }) => {
    const res = await request.post(`${API_URL}/api/v1/posts`, {
      headers: apiHeaders("free"),
      data: {
        content: "API E2E workflow test post",
        platforms: ["x_twitter"],
      },
    });
    expect([200, 201]).toContain(res.status());
    const body = await res.json();
    expect(body).toHaveProperty("id");
  });

  test("usage endpoint returns quota info", async ({ request }) => {
    const res = await request.get(`${API_URL}/api/v1/usage`, {
      headers: apiHeaders("free"),
    });
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(body).toHaveProperty("posts_used");
    expect(body).toHaveProperty("posts_limit");
  });

  test("webhook registration works", async ({ request }) => {
    const res = await request.post(`${API_URL}/api/v1/webhooks`, {
      headers: apiHeaders("free"),
      data: {
        url: "https://example.com/webhook/e2e",
        events: ["post.published"],
      },
    });
    expect([200, 201]).toContain(res.status());
  });

  test("user profile endpoint works", async ({ request }) => {
    const res = await request.get(`${API_URL}/api/v1/users/me`, {
      headers: apiHeaders("free"),
    });
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(body).toHaveProperty("email");
    expect(body).toHaveProperty("language");
  });

  test("unauthorized request returns 401", async ({ request }) => {
    const res = await request.get(`${API_URL}/api/v1/usage`, {
      headers: { "Content-Type": "application/json" },
    });
    expect(res.status()).toBe(401);
  });
});
