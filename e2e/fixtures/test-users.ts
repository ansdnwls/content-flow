/** Test user accounts seeded before E2E runs. */

export const TEST_USERS = {
  free: {
    email: "test_free@contentflow.dev",
    password: "TestPass123!",
    plan: "free",
    apiKey: "cf_live_test_free_000000000000",
  },
  build: {
    email: "test_build@contentflow.dev",
    password: "TestPass123!",
    plan: "build",
    apiKey: "cf_live_test_build_00000000000",
  },
  scale: {
    email: "test_scale@contentflow.dev",
    password: "TestPass123!",
    plan: "scale",
    apiKey: "cf_live_test_scale_00000000000",
  },
} as const;

export type TestUserPlan = keyof typeof TEST_USERS;
