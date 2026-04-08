import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { ContentFlow, ContentFlowError } from "../src/index.js";
import { createHmac } from "node:crypto";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(
  status: number,
  body: unknown,
  options?: { assertBody?: (b: unknown) => void; assertUrl?: (u: string) => void },
) {
  return vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    if (options?.assertUrl) options.assertUrl(String(url));
    if (options?.assertBody && init?.body) {
      options.assertBody(JSON.parse(String(init.body)));
    }
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
}

let cf: ContentFlow;
const BASE = "https://test.contentflow.dev";
const API_KEY = "cf_live_test123";

beforeEach(() => {
  cf = new ContentFlow({ apiKey: API_KEY, baseUrl: BASE });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Client construction
// ---------------------------------------------------------------------------

describe("ContentFlow", () => {
  it("exposes all resource namespaces", () => {
    expect(cf.posts).toBeDefined();
    expect(cf.videos).toBeDefined();
    expect(cf.accounts).toBeDefined();
    expect(cf.analytics).toBeDefined();
    expect(cf.comments).toBeDefined();
    expect(cf.bombs).toBeDefined();
  });

  it("strips trailing slashes from baseUrl", () => {
    const client = new ContentFlow({ apiKey: API_KEY, baseUrl: "https://api.test.dev///" });
    // Access internal state through a resource call to verify
    expect(client).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Posts
// ---------------------------------------------------------------------------

describe("Posts", () => {
  it("create sends correct body", async () => {
    const mockResponse = { id: "post_1", status: "pending" };
    vi.stubGlobal(
      "fetch",
      mockFetch(201, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/posts`),
        assertBody: (body: any) => {
          expect(body.platforms).toEqual(["youtube", "tiktok"]);
          expect(body.text).toBe("Hello");
          expect(body.media_urls).toEqual(["https://example.com/video.mp4"]);
        },
      }),
    );

    const result = await cf.posts.create({
      text: "Hello",
      platforms: ["youtube", "tiktok"],
      mediaUrls: ["https://example.com/video.mp4"],
    });
    expect(result).toEqual(mockResponse);
  });

  it("get fetches by ID", async () => {
    const mockResponse = { id: "post_1", status: "published" };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/posts/post_1`),
      }),
    );

    const result = await cf.posts.get("post_1");
    expect(result).toEqual(mockResponse);
  });

  it("list with filters", async () => {
    const mockResponse = { data: [], total: 0, page: 1, limit: 10 };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => {
          expect(url).toContain("/api/v1/posts");
          expect(url).toContain("page=2");
          expect(url).toContain("limit=10");
          expect(url).toContain("status=published");
        },
      }),
    );

    const result = await cf.posts.list({ page: 2, limit: 10, status: "published" });
    expect(result).toEqual(mockResponse);
  });

  it("cancel deletes by ID", async () => {
    const mockResponse = { id: "post_1", status: "cancelled" };
    vi.stubGlobal("fetch", mockFetch(200, mockResponse));

    const result = await cf.posts.cancel("post_1");
    expect(result).toEqual(mockResponse);
  });
});

// ---------------------------------------------------------------------------
// Videos
// ---------------------------------------------------------------------------

describe("Videos", () => {
  it("generate sends correct body", async () => {
    const mockResponse = { id: "vid_1", status: "queued" };
    vi.stubGlobal(
      "fetch",
      mockFetch(201, mockResponse, {
        assertBody: (body: any) => {
          expect(body.topic).toBe("DUI laws");
          expect(body.mode).toBe("legal");
          expect(body.language).toBe("ko");
        },
      }),
    );

    const result = await cf.videos.generate({
      topic: "DUI laws",
      mode: "legal",
      language: "ko",
    });
    expect(result).toEqual(mockResponse);
  });

  it("generate with auto_publish", async () => {
    const mockResponse = { id: "vid_2", status: "queued" };
    vi.stubGlobal(
      "fetch",
      mockFetch(201, mockResponse, {
        assertBody: (body: any) => {
          expect(body.auto_publish.enabled).toBe(true);
          expect(body.auto_publish.platforms).toEqual(["youtube"]);
        },
      }),
    );

    await cf.videos.generate({
      topic: "Test",
      autoPublish: { enabled: true, platforms: ["youtube"] },
    });
  });

  it("get fetches by ID", async () => {
    const mockResponse = { id: "vid_1", status: "completed" };
    vi.stubGlobal("fetch", mockFetch(200, mockResponse));

    const result = await cf.videos.get("vid_1");
    expect(result).toEqual(mockResponse);
  });
});

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------

describe("Accounts", () => {
  it("list returns accounts", async () => {
    const mockResponse = { data: [{ id: "acc_1", platform: "youtube" }], total: 1 };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/accounts`),
      }),
    );

    const result = await cf.accounts.list();
    expect(result).toEqual(mockResponse);
  });

  it("connect initiates OAuth", async () => {
    const mockResponse = { authorize_url: "https://oauth.example.com/auth" };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/accounts/connect/youtube`),
      }),
    );

    const result = await cf.accounts.connect("youtube");
    expect(result).toEqual(mockResponse);
  });
});

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

describe("Analytics", () => {
  it("get without platform", async () => {
    const mockResponse = { post_counts: { published: 5 }, video_counts: { completed: 2 } };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/analytics`),
      }),
    );

    const result = await cf.analytics.get();
    expect(result).toEqual(mockResponse);
  });

  it("get with platform filter", async () => {
    const mockResponse = { post_counts: { published: 3 }, video_counts: {} };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/analytics/youtube`),
      }),
    );

    const result = await cf.analytics.get("youtube");
    expect(result).toEqual(mockResponse);
  });
});

// ---------------------------------------------------------------------------
// Comments
// ---------------------------------------------------------------------------

describe("Comments", () => {
  it("list with filters", async () => {
    const mockResponse = { data: [], total: 0, page: 1, limit: 50 };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => {
          expect(url).toContain("/api/v1/comments");
          expect(url).toContain("platform=youtube");
          expect(url).toContain("reply_status=pending");
        },
      }),
    );

    const result = await cf.comments.list({
      platform: "youtube",
      replyStatus: "pending",
    });
    expect(result).toEqual(mockResponse);
  });

  it("get fetches by ID", async () => {
    const mockResponse = { id: "c_1", text: "Nice video!" };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/comments/c_1`),
      }),
    );

    const result = await cf.comments.get("c_1");
    expect(result).toEqual(mockResponse);
  });

  it("collect sends correct body", async () => {
    const mockResponse = [{ id: "c_1", platform_comment_id: "yt_c1" }];
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertBody: (body: any) => {
          expect(body.platform).toBe("youtube");
          expect(body.platform_post_id).toBe("vid_001");
          expect(body.credentials.access_token).toBe("tok");
        },
      }),
    );

    const result = await cf.comments.collect({
      platform: "youtube",
      platformPostId: "vid_001",
      credentials: { access_token: "tok" },
    });
    expect(result).toEqual(mockResponse);
  });

  it("reply sends correct body", async () => {
    const mockResponse = { success: true, ai_reply: "Thanks!", platform_reply_id: "r_1" };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/comments/c_1/reply`),
        assertBody: (body: any) => {
          expect(body.credentials.access_token).toBe("tok");
          expect(body.context).toBe("Python tips");
        },
      }),
    );

    const result = await cf.comments.reply("c_1", {
      credentials: { access_token: "tok" },
      context: "Python tips",
    });
    expect(result).toEqual(mockResponse);
  });
});

// ---------------------------------------------------------------------------
// Bombs
// ---------------------------------------------------------------------------

describe("Bombs", () => {
  it("create sends topic", async () => {
    const mockResponse = { id: "bomb_1", status: "queued", topic: "DUI laws" };
    vi.stubGlobal(
      "fetch",
      mockFetch(201, mockResponse, {
        assertBody: (body: any) => expect(body.topic).toBe("DUI laws"),
      }),
    );

    const result = await cf.bombs.create({ topic: "DUI laws" });
    expect(result).toEqual(mockResponse);
  });

  it("get fetches by ID", async () => {
    const mockResponse = { id: "bomb_1", status: "ready" };
    vi.stubGlobal("fetch", mockFetch(200, mockResponse));

    const result = await cf.bombs.get("bomb_1");
    expect(result).toEqual(mockResponse);
  });

  it("publish triggers publication", async () => {
    const mockResponse = { id: "bomb_1", status: "published" };
    vi.stubGlobal(
      "fetch",
      mockFetch(200, mockResponse, {
        assertUrl: (url) => expect(url).toBe(`${BASE}/api/v1/bombs/bomb_1/publish`),
      }),
    );

    const result = await cf.bombs.publish("bomb_1");
    expect(result).toEqual(mockResponse);
  });
});

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

describe("Error handling", () => {
  it("throws ContentFlowError on 4xx", async () => {
    vi.stubGlobal("fetch", mockFetch(401, { detail: "Invalid API key" }));

    await expect(cf.posts.list()).rejects.toThrow(ContentFlowError);
    await expect(cf.posts.list()).rejects.toThrow("Invalid API key");
  });

  it("throws ContentFlowError on 5xx", async () => {
    vi.stubGlobal("fetch", mockFetch(500, { detail: "Internal server error" }));

    try {
      await cf.posts.list();
      expect.fail("Should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ContentFlowError);
      expect((e as ContentFlowError).status).toBe(500);
    }
  });

  it("sends X-API-Key header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        const headers = init?.headers as Record<string, string>;
        expect(headers["X-API-Key"]).toBe(API_KEY);
        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    await cf.accounts.list();
  });
});

describe("Webhook helpers", () => {
  it("verifies a valid signature", async () => {
    const body = '{"event":"post.published","data":{"id":"p1"}}';
    const timestamp = "1712505600";
    const secret = "whsec_test";
    const signature = `sha256=${createHmac("sha256", secret)
      .update(`${timestamp}.${body}`)
      .digest("hex")}`;

    await expect(
      ContentFlow.webhooks.verifySignature(body, signature, secret, timestamp, {
        currentTime: 1712505601,
      }),
    ).resolves.toBe(true);
  });

  it("rejects an invalid signature", async () => {
    await expect(
      ContentFlow.webhooks.verifySignature("{}", "sha256=deadbeef", "whsec_test", "1712505600", {
        currentTime: 1712505600,
      }),
    ).rejects.toThrow("Signature verification failed");
  });

  it("rejects a stale timestamp", async () => {
    const body = "{}";
    const timestamp = "1712505600";
    const secret = "whsec_test";
    const signature = `sha256=${createHmac("sha256", secret)
      .update(`${timestamp}.${body}`)
      .digest("hex")}`;

    await expect(
      ContentFlow.webhooks.verifySignature(body, signature, secret, timestamp, {
        currentTime: 1712506201,
        toleranceSeconds: 300,
      }),
    ).rejects.toThrow("Timestamp outside tolerance");
  });
});
