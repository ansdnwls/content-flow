import { test, expect } from "@playwright/test";
import { createPostViaApi } from "../../helpers/api-helper";

test.describe("Bulk Posts API", () => {
  test("can create a post via API", async ({ request }) => {
    const res = await createPostViaApi(request, {
      content: "Bulk E2E test post",
      platforms: ["x_twitter"],
    });
    // API may return 200 or 201 depending on mock/real
    expect([200, 201]).toContain(res.status());
  });
});
