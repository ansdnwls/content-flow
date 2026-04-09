"""ContentFlow SDK type definitions (Pydantic models)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Posts ────────────────────────────────────────────────────────


class PlatformStatus(BaseModel):
    """Per-platform delivery status."""

    status: str
    platform_post_id: str | None = None


class Post(BaseModel):
    """A multi-platform publishing job."""

    id: str
    status: str
    text: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    media_type: str = "text"
    scheduled_for: str | None = None
    platforms: dict[str, PlatformStatus] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PostList(BaseModel):
    """Paginated list of posts."""

    data: list[Post] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20


class CreatePostRequest(BaseModel):
    """Request body for creating a post."""

    platforms: list[str]
    text: str | None = None
    media_urls: list[str] | None = None
    media_type: str = "text"
    scheduled_for: str | None = None
    platform_options: dict[str, Any] | None = None


# ── Videos ───────────────────────────────────────────────────────


class AutoPublish(BaseModel):
    """Auto-publish configuration for video generation."""

    enabled: bool = False
    platforms: list[str] = Field(default_factory=list)
    scheduled_for: str | None = None


class Video(BaseModel):
    """A video generation job."""

    id: str
    topic: str
    mode: str = "general"
    status: str = "pending"
    provider_job_id: str | None = None
    output_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GenerateVideoRequest(BaseModel):
    """Request body for generating a video."""

    topic: str
    mode: str = "general"
    language: str = "ko"
    format: str = "shorts"
    style: str = "realistic"
    auto_publish: AutoPublish | None = None


# ── Accounts ─────────────────────────────────────────────────────


class Account(BaseModel):
    """A connected social media account."""

    id: str
    platform: str
    handle: str
    display_name: str | None = None
    token_expires_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccountList(BaseModel):
    """List of connected accounts."""

    data: list[Account] = Field(default_factory=list)
    total: int = 0


class ConnectResponse(BaseModel):
    """OAuth authorization URL response."""

    authorize_url: str


# ── Analytics ────────────────────────────────────────────────────


class AnalyticsDashboard(BaseModel):
    """Aggregated analytics metrics for a period."""

    period: str = "7d"
    days: int = 7
    snapshot_count: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_impressions: int = 0
    total_reach: int = 0
    engagement_rate: float = 0.0


class AnalyticsSummary(BaseModel):
    """Counts of posts and videos by status."""

    post_counts: dict[str, int] = Field(default_factory=dict)
    video_counts: dict[str, int] = Field(default_factory=dict)


class PlatformMetrics(BaseModel):
    """Per-platform aggregated metrics."""

    platform: str
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_impressions: int = 0
    total_reach: int = 0
    engagement_rate: float = 0.0


class TopPost(BaseModel):
    """A top-performing post."""

    platform: str
    platform_post_id: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    engagement_rate: float = 0.0
    snapshot_date: str | None = None


# ── Webhooks ─────────────────────────────────────────────────────


class WebhookDelivery(BaseModel):
    """A webhook delivery attempt."""

    id: str
    webhook_id: str
    event_type: str
    status_code: int | None = None
    success: bool = False
    created_at: datetime | None = None


class WebhookEvent(BaseModel):
    """An incoming webhook event payload."""

    id: str
    event_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None
