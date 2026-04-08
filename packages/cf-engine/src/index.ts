import type { VerticalConfig } from "@contentflow/config";

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface CFEngineOptions {
  readonly apiUrl?: string;
  readonly apiKey?: string;
  readonly config?: VerticalConfig;
}

export interface ApiResponse<T> {
  readonly data: T | null;
  readonly error: string | null;
  readonly status: number;
}

// --- YtBoost types ---

export interface YtBoostChannel {
  readonly id: string;
  readonly user_id: string;
  readonly youtube_channel_id: string;
  readonly channel_name: string | null;
  readonly subscribed_at: string;
  readonly auto_distribute: boolean;
  readonly target_platforms: readonly string[];
  readonly auto_comment_mode: string;
}

export interface YtBoostShort {
  readonly id: string;
  readonly source_video_id: string;
  readonly source_channel_id: string;
  readonly start_seconds: number;
  readonly end_seconds: number;
  readonly hook_line: string | null;
  readonly suggested_title: string | null;
  readonly status: string;
  readonly created_at: string;
}

export interface ShortsListResponse {
  readonly data: readonly YtBoostShort[];
  readonly total: number;
}

export interface PendingComment {
  readonly id: string;
  readonly platform: string;
  readonly platform_post_id: string;
  readonly author_name: string;
  readonly text: string;
  readonly ai_reply: string | null;
  readonly reply_status: string;
  readonly created_at: string;
}

export interface PendingCommentListResponse {
  readonly data: readonly PendingComment[];
  readonly total: number;
}

// --- ShopSync types ---

export interface ShopProduct {
  readonly id: string;
  readonly name: string;
  readonly price: number;
  readonly image_urls: readonly string[];
  readonly status: string;
  readonly platforms_published: readonly string[];
  readonly created_at: string;
}

export interface ProductListResponse {
  readonly data: readonly ShopProduct[];
  readonly total: number;
}

export class CFEngine {
  private readonly apiUrl: string;
  private readonly apiKey: string;
  private readonly config: VerticalConfig | null;

  constructor(options: CFEngineOptions = {}) {
    this.apiUrl = options.apiUrl ?? DEFAULT_API_URL;
    this.apiKey = options.apiKey ?? "";
    this.config = options.config ?? null;
  }

  get verticalId(): string | null {
    return this.config?.id ?? null;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }
    if (this.config?.id) {
      headers["X-Vertical-Id"] = this.config.id;
    }

    try {
      const res = await fetch(`${this.apiUrl}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json();
      if (!res.ok) {
        return { data: null, error: data.detail ?? "Request failed", status: res.status };
      }
      return { data: data as T, error: null, status: res.status };
    } catch (err) {
      const message = err instanceof Error ? err.message : "Network error";
      return { data: null, error: message, status: 0 };
    }
  }

  // --- General ---

  async getPosts() {
    return this.request<unknown[]>("GET", "/api/v1/posts");
  }

  async createPost(post: Record<string, unknown>) {
    return this.request<unknown>("POST", "/api/v1/posts", post);
  }

  async getAccounts() {
    return this.request<unknown[]>("GET", "/api/v1/accounts");
  }

  async getUsage() {
    return this.request<unknown>("GET", "/api/v1/usage");
  }

  async getAnalytics(period: string = "7d") {
    return this.request<unknown>("GET", `/api/v1/analytics?period=${period}`);
  }

  // --- YtBoost ---

  async listChannels() {
    return this.request<YtBoostChannel[]>("GET", "/api/v1/ytboost/channels");
  }

  async subscribeChannel(channelId: string, channelName?: string) {
    return this.request<YtBoostChannel>("POST", "/api/v1/ytboost/channels", {
      youtube_channel_id: channelId,
      channel_name: channelName,
    });
  }

  async extractShorts(videoId: string, channelId: string) {
    return this.request<ShortsListResponse>("POST", "/api/v1/ytboost/shorts/extract", {
      video_id: videoId,
      source_channel_id: channelId,
    });
  }

  async listShorts(status?: string) {
    const qs = status ? `?status=${status}` : "";
    return this.request<ShortsListResponse>("GET", `/api/v1/ytboost/shorts${qs}`);
  }

  async approveShort(shortId: string, platforms?: string[]) {
    return this.request<unknown>("POST", `/api/v1/ytboost/shorts/${shortId}/approve`, {
      target_platforms: platforms,
    });
  }

  async rejectShort(shortId: string) {
    return this.request<YtBoostShort>("POST", `/api/v1/ytboost/shorts/${shortId}/reject`);
  }

  async listPendingComments() {
    return this.request<PendingCommentListResponse>("GET", "/api/v1/ytboost/comments/pending");
  }

  async approveComment(commentId: string, text?: string) {
    return this.request<unknown>("POST", `/api/v1/ytboost/comments/${commentId}/approve`, {
      text,
    });
  }

  // --- ShopSync ---

  async listProducts(page: number = 1, limit: number = 20) {
    return this.request<ProductListResponse>(
      "GET",
      `/api/v1/posts?page=${page}&limit=${limit}`,
    );
  }

  async createProduct(product: {
    name: string;
    price: number;
    image_urls?: string[];
    platforms?: string[];
  }) {
    return this.request<unknown>("POST", "/api/v1/bombs", {
      product_name: product.name,
      price: product.price,
      image_urls: product.image_urls ?? [],
      target_platforms: product.platforms,
    });
  }

  async publishProduct(bombId: string) {
    return this.request<unknown>("POST", `/api/v1/bombs/${bombId}/publish`);
  }
}

export function createEngine(options?: CFEngineOptions): CFEngine {
  return new CFEngine(options);
}
