/**
 * ContentFlow SDK — JavaScript/TypeScript client for the ContentFlow API.
 *
 * Works in Node.js 18+ and modern browsers (uses native fetch).
 *
 * @example
 * ```ts
 * const cf = new ContentFlow({ apiKey: "cf_live_xxx" });
 * const post = await cf.posts.create({
 *   text: "Hello",
 *   platforms: ["youtube", "tiktok"],
 *   mediaUrls: ["https://example.com/video.mp4"],
 * });
 * ```
 */

import * as webhooks from "./webhooks.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ContentFlowOptions {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
}

export interface CreatePostParams {
  text?: string;
  platforms: string[];
  mediaUrls?: string[];
  mediaType?: string;
  scheduledFor?: string;
  platformOptions?: Record<string, unknown>;
}

export interface ListPostsParams {
  page?: number;
  limit?: number;
  status?: string;
}

export interface GenerateVideoParams {
  topic: string;
  mode?: string;
  language?: string;
  format?: string;
  style?: string;
  autoPublish?: {
    enabled: boolean;
    platforms: string[];
    scheduledFor?: string;
  };
}

export interface ListCommentsParams {
  platform?: string;
  platformPostId?: string;
  replyStatus?: string;
  page?: number;
  limit?: number;
}

export interface ReplyCommentParams {
  credentials: Record<string, string>;
  context?: string;
}

export interface CollectCommentsParams {
  platform: string;
  platformPostId: string;
  credentials: Record<string, string>;
}

export interface CreateBombParams {
  topic: string;
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export class ContentFlowError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(message);
    this.name = "ContentFlowError";
  }
}

// ---------------------------------------------------------------------------
// HTTP core
// ---------------------------------------------------------------------------

const DEFAULT_BASE_URL = "https://api.contentflow.dev";
const DEFAULT_TIMEOUT = 30_000;

type HttpMethod = "GET" | "POST" | "DELETE";

async function request(
  baseUrl: string,
  apiKey: string,
  timeout: number,
  method: HttpMethod,
  path: string,
  options?: {
    body?: Record<string, unknown>;
    params?: Record<string, string | number | undefined>;
  },
): Promise<unknown> {
  let url = `${baseUrl}${path}`;

  if (options?.params) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined) {
        search.set(key, String(value));
      }
    }
    const qs = search.toString();
    if (qs) url += `?${qs}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const resp = await fetch(url, {
      method,
      headers: {
        "X-API-Key": apiKey,
        "Content-Type": "application/json",
      },
      body: options?.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    const data: unknown = await resp.json().catch(() => null);

    if (!resp.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? String((data as Record<string, unknown>).detail)
          : `HTTP ${resp.status}`;
      throw new ContentFlowError(detail, resp.status, data);
    }

    return data;
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Resource classes
// ---------------------------------------------------------------------------

class PostsResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
    private readonly timeout: number,
  ) {}

  async create(params: CreatePostParams): Promise<unknown> {
    const body: Record<string, unknown> = {
      platforms: params.platforms,
    };
    if (params.text !== undefined) body.text = params.text;
    if (params.mediaUrls?.length) {
      body.media_urls = params.mediaUrls;
      body.media_type = params.mediaType ?? "video";
    }
    if (params.scheduledFor) body.scheduled_for = params.scheduledFor;
    if (params.platformOptions) body.platform_options = params.platformOptions;
    return request(this.baseUrl, this.apiKey, this.timeout, "POST", "/api/v1/posts", { body });
  }

  async get(postId: string): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "GET", `/api/v1/posts/${postId}`);
  }

  async list(params?: ListPostsParams): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "GET", "/api/v1/posts", {
      params: {
        page: params?.page,
        limit: params?.limit,
        status: params?.status,
      },
    });
  }

  async cancel(postId: string): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "DELETE", `/api/v1/posts/${postId}`);
  }
}

class VideosResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
    private readonly timeout: number,
  ) {}

  async generate(params: GenerateVideoParams): Promise<unknown> {
    const body: Record<string, unknown> = {
      topic: params.topic,
      mode: params.mode ?? "general",
      language: params.language ?? "ko",
      format: params.format ?? "shorts",
      style: params.style ?? "realistic",
    };
    if (params.autoPublish) {
      body.auto_publish = {
        enabled: params.autoPublish.enabled,
        platforms: params.autoPublish.platforms,
        scheduled_for: params.autoPublish.scheduledFor,
      };
    }
    return request(this.baseUrl, this.apiKey, this.timeout, "POST", "/api/v1/videos/generate", {
      body,
    });
  }

  async get(videoId: string): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "GET", `/api/v1/videos/${videoId}`);
  }
}

class AccountsResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
    private readonly timeout: number,
  ) {}

  async list(): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "GET", "/api/v1/accounts");
  }

  async connect(platform: string): Promise<unknown> {
    return request(
      this.baseUrl,
      this.apiKey,
      this.timeout,
      "POST",
      `/api/v1/accounts/connect/${platform}`,
    );
  }
}

class AnalyticsResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
    private readonly timeout: number,
  ) {}

  async get(platform?: string): Promise<unknown> {
    const path = platform ? `/api/v1/analytics/${platform}` : "/api/v1/analytics";
    return request(this.baseUrl, this.apiKey, this.timeout, "GET", path);
  }
}

class CommentsResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
    private readonly timeout: number,
  ) {}

  async list(params?: ListCommentsParams): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "GET", "/api/v1/comments", {
      params: {
        platform: params?.platform,
        platform_post_id: params?.platformPostId,
        reply_status: params?.replyStatus,
        page: params?.page,
        limit: params?.limit,
      },
    });
  }

  async get(commentId: string): Promise<unknown> {
    return request(
      this.baseUrl,
      this.apiKey,
      this.timeout,
      "GET",
      `/api/v1/comments/${commentId}`,
    );
  }

  async collect(params: CollectCommentsParams): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "POST", "/api/v1/comments/collect", {
      body: {
        platform: params.platform,
        platform_post_id: params.platformPostId,
        credentials: params.credentials,
      },
    });
  }

  async reply(commentId: string, params: ReplyCommentParams): Promise<unknown> {
    return request(
      this.baseUrl,
      this.apiKey,
      this.timeout,
      "POST",
      `/api/v1/comments/${commentId}/reply`,
      {
        body: {
          credentials: params.credentials,
          context: params.context ?? "",
        },
      },
    );
  }
}

class BombsResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
    private readonly timeout: number,
  ) {}

  async create(params: CreateBombParams): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "POST", "/api/v1/bombs", {
      body: { topic: params.topic },
    });
  }

  async get(bombId: string): Promise<unknown> {
    return request(this.baseUrl, this.apiKey, this.timeout, "GET", `/api/v1/bombs/${bombId}`);
  }

  async publish(bombId: string): Promise<unknown> {
    return request(
      this.baseUrl,
      this.apiKey,
      this.timeout,
      "POST",
      `/api/v1/bombs/${bombId}/publish`,
    );
  }
}

// ---------------------------------------------------------------------------
// Main client
// ---------------------------------------------------------------------------

export class ContentFlow {
  public readonly posts: PostsResource;
  public readonly videos: VideosResource;
  public readonly accounts: AccountsResource;
  public readonly analytics: AnalyticsResource;
  public readonly comments: CommentsResource;
  public readonly bombs: BombsResource;
  public static readonly webhooks = webhooks;

  constructor(options: ContentFlowOptions) {
    const baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    const timeout = options.timeout ?? DEFAULT_TIMEOUT;

    this.posts = new PostsResource(baseUrl, options.apiKey, timeout);
    this.videos = new VideosResource(baseUrl, options.apiKey, timeout);
    this.accounts = new AccountsResource(baseUrl, options.apiKey, timeout);
    this.analytics = new AnalyticsResource(baseUrl, options.apiKey, timeout);
    this.comments = new CommentsResource(baseUrl, options.apiKey, timeout);
    this.bombs = new BombsResource(baseUrl, options.apiKey, timeout);
  }
}

export {
  verifySignature,
  VerifySignatureOptions,
  WebhookVerificationError,
} from "./webhooks.js";

export default ContentFlow;
