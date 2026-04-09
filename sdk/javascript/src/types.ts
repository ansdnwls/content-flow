/**
 * ContentFlow SDK — Shared type definitions.
 *
 * These types mirror the API response shapes and can be used for
 * stricter typing on top of the base client (which returns `unknown`).
 */

// ---------------------------------------------------------------------------
// Posts
// ---------------------------------------------------------------------------

export interface PlatformStatus {
  status: string;
  platform_post_id?: string;
}

export interface Post {
  id: string;
  status: string;
  text?: string;
  media_urls: string[];
  media_type: string;
  scheduled_for?: string;
  platforms: Record<string, PlatformStatus>;
  created_at: string;
  updated_at: string;
}

export interface PostList {
  data: Post[];
  total: number;
  page: number;
  limit: number;
}

// ---------------------------------------------------------------------------
// Videos
// ---------------------------------------------------------------------------

export interface AutoPublishConfig {
  enabled: boolean;
  platforms: string[];
  scheduled_for?: string;
}

export interface Video {
  id: string;
  topic: string;
  mode: string;
  status: string;
  provider_job_id?: string;
  output_url?: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------

export interface Account {
  id: string;
  platform: string;
  handle: string;
  display_name?: string;
  token_expires_at?: string;
  metadata: Record<string, unknown>;
}

export interface AccountList {
  data: Account[];
  total: number;
}

export interface ConnectResponse {
  authorize_url: string;
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export interface AnalyticsDashboard {
  period: string;
  days: number;
  snapshot_count: number;
  total_views: number;
  total_likes: number;
  total_comments: number;
  total_shares: number;
  total_impressions: number;
  total_reach: number;
  engagement_rate: number;
}

export interface AnalyticsSummary {
  post_counts: Record<string, number>;
  video_counts: Record<string, number>;
}

export interface PlatformMetrics {
  platform: string;
  total_views: number;
  total_likes: number;
  total_comments: number;
  total_shares: number;
  total_impressions: number;
  total_reach: number;
  engagement_rate: number;
}

export interface TopPost {
  platform: string;
  platform_post_id: string;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  engagement_rate: number;
  snapshot_date?: string;
}

// ---------------------------------------------------------------------------
// Webhooks
// ---------------------------------------------------------------------------

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event_type: string;
  status_code?: number;
  success: boolean;
  created_at: string;
}

export interface WebhookEvent {
  id: string;
  event_type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Comments
// ---------------------------------------------------------------------------

export interface Comment {
  id: string;
  platform: string;
  platform_post_id: string;
  author_name: string;
  text: string;
  reply_status: string;
  ai_reply?: string;
  created_at: string;
}

export interface CommentList {
  data: Comment[];
  total: number;
  page: number;
  limit: number;
}

// ---------------------------------------------------------------------------
// Bombs
// ---------------------------------------------------------------------------

export interface Bomb {
  id: string;
  topic: string;
  status: string;
  posts: Post[];
  created_at: string;
}
