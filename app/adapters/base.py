"""Platform adapter interface — all adapters implement this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PublishResult:
    success: bool
    platform_post_id: str | None = None
    url: str | None = None
    error: str | None = None
    raw_response: dict | None = None


@dataclass(frozen=True)
class MediaSpec:
    url: str
    media_type: str  # "video" | "image"


@dataclass(frozen=True)
class Comment:
    platform_comment_id: str
    author_id: str
    author_name: str
    text: str
    created_at: datetime
    parent_id: str | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class ReplyResult:
    success: bool
    platform_comment_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AnalyticsData:
    """Platform-level analytics snapshot for a single post or account."""

    platform: str
    platform_post_id: str | None = None
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    followers: int = 0
    impressions: int = 0
    reach: int = 0
    engagement_rate: float = 0.0
    raw: dict | None = None


@dataclass(frozen=True)
class RateLimitCheckResult:
    allowed: bool
    remaining: int
    limit: int
    units_requested: int
    next_available_at: str | None = None
    retry_after_seconds: int = 0


class PlatformAdapter(ABC):
    """Base class for all social platform adapters."""

    platform_name: str

    @abstractmethod
    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        """Publish content to the platform. Returns a PublishResult."""
        ...

    @abstractmethod
    async def delete(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
    ) -> bool:
        """Delete a published post. Returns True if successful."""
        ...

    @abstractmethod
    async def validate_credentials(
        self,
        credentials: dict[str, str],
    ) -> bool:
        """Check if credentials are still valid."""
        ...

    async def rate_limit_check(
        self,
        owner_id: str,
        social_account_id: str | None = None,
        *,
        reserve: bool = False,
    ) -> RateLimitCheckResult:
        """Check or reserve a platform-specific publish slot before dispatch."""
        from app.core.platform_limiter import check_platform_limit

        decision = await check_platform_limit(
            self.platform_name,
            owner_id,
            social_account_id,
            reserve=reserve,
        )
        return RateLimitCheckResult(
            allowed=decision.allowed,
            remaining=decision.remaining,
            limit=decision.limit,
            units_requested=decision.units_requested,
            next_available_at=decision.next_available_at,
            retry_after_seconds=decision.retry_after_seconds,
        )

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        """Fetch comments for a post. Override in adapters that support comments."""
        raise NotImplementedError(
            f"{self.platform_name} does not support fetching comments"
        )

    async def reply_comment(
        self,
        platform_post_id: str,
        comment_id: str,
        text: str,
        credentials: dict[str, str],
    ) -> ReplyResult:
        """Reply to a comment. Override in adapters that support replies."""
        raise NotImplementedError(
            f"{self.platform_name} does not support replying to comments"
        )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        """Fetch analytics data. Override in adapters that support analytics."""
        raise NotImplementedError(
            f"{self.platform_name} does not support analytics"
        )
