import { type APIRequestContext } from "@playwright/test";
import { TEST_USERS, type TestUserPlan } from "../fixtures/test-users";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

function headers(plan: TestUserPlan = "free") {
  return {
    "Content-Type": "application/json",
    "X-API-Key": TEST_USERS[plan].apiKey,
  };
}

/**
 * Create a post via the API.
 */
export async function createPostViaApi(
  request: APIRequestContext,
  data: {
    content: string;
    platforms: string[];
    title?: string;
    scheduled_for?: string;
  },
  plan: TestUserPlan = "free",
) {
  const res = await request.post(`${API_URL}/api/v1/posts`, {
    headers: headers(plan),
    data,
  });
  return res;
}

/**
 * Create a video via the API.
 */
export async function createVideoViaApi(
  request: APIRequestContext,
  data: {
    topic: string;
    mode: string;
    language?: string;
    template_id?: string;
    auto_publish?: boolean;
  },
  plan: TestUserPlan = "free",
) {
  const res = await request.post(`${API_URL}/api/v1/videos`, {
    headers: headers(plan),
    data,
  });
  return res;
}

/**
 * Get usage stats via the API.
 */
export async function getUsage(
  request: APIRequestContext,
  plan: TestUserPlan = "free",
) {
  const res = await request.get(`${API_URL}/api/v1/usage`, {
    headers: headers(plan),
  });
  return res;
}

/**
 * Create a webhook via the API.
 */
export async function createWebhookViaApi(
  request: APIRequestContext,
  data: { url: string; events: string[] },
  plan: TestUserPlan = "free",
) {
  const res = await request.post(`${API_URL}/api/v1/webhooks`, {
    headers: headers(plan),
    data,
  });
  return res;
}
