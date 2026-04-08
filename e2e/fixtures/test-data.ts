/** Reusable test data for E2E specs. */

export const SAMPLE_POST = {
  title: "E2E Test Post",
  content: "This is an automated E2E test post created by Playwright.",
  platforms: ["x_twitter", "linkedin"],
};

export const SAMPLE_VIDEO = {
  topic: "How AI is transforming legal workflows",
  mode: "legal",
  language: "en",
  template: "cinematic",
};

export const SAMPLE_WEBHOOK = {
  url: "https://example.com/webhook/e2e-test",
  events: ["post.created", "post.published"],
};

export const SAMPLE_API_KEY_NAME = "E2E Test Key";
