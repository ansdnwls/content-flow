"""Platform adapter interface — all adapters implement this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
