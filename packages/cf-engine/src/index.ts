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
      headers["Authorization"] = `Bearer ${this.apiKey}`;
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
}

export function createEngine(options?: CFEngineOptions): CFEngine {
  return new CFEngine(options);
}
