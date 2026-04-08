"""YtBoost short distribution built on top of ContentFlow posting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.api.v1.posts import CreatePostRequest, create_internal_post


@dataclass(frozen=True)
class DistributionResult:
    requested_platform: str
    adapter_platform: str
    status: str
    post_id: str | None = None


class YtBoostDistributor:
    """Map YtBoost distribution targets onto existing platform adapters."""

    PLATFORM_MAP: dict[str, dict[str, Any]] = {
        "youtube_shorts": {"adapter": "youtube", "options": {"is_short": True}},
        "instagram_reels": {"adapter": "instagram", "options": {"media_type": "REELS"}},
        "tiktok": {"adapter": "tiktok", "options": {}},
        "x": {"adapter": "x_twitter", "options": {"with_media": True}},
        "threads": {"adapter": "threads", "options": {}},
        "facebook_reels": {"adapter": "facebook", "options": {"media_type": "REELS"}},
    }

    async def distribute_short(
        self,
        short_clip: dict[str, Any],
        target_platforms: list[str],
        user_id: str,
    ) -> list[DistributionResult]:
        platform_options: dict[str, Any] = {}
        mapped_platforms: list[str] = []
        results: list[DistributionResult] = []

        for target in target_platforms:
            mapping = self.PLATFORM_MAP.get(target)
            if not mapping:
                results.append(
                    DistributionResult(
                        requested_platform=target,
                        adapter_platform=target,
                        status="unsupported",
                    ),
                )
                continue
            adapter_platform = mapping["adapter"]
            mapped_platforms.append(adapter_platform)
            platform_options[adapter_platform] = mapping["options"]

        if not mapped_platforms:
            return results

        hashtags = " ".join(short_clip.get("suggested_hashtags") or [])
        text = short_clip.get("suggested_title") or short_clip.get("hook_line") or "YtBoost short"
        if hashtags:
            text = f"{text}\n\n{hashtags}".strip()

        post = await create_internal_post(
            user_id,
            CreatePostRequest(
                text=text,
                platforms=mapped_platforms,
                media_urls=[short_clip.get("clip_file_url") or ""],
                media_type="video",
                platform_options=platform_options,
            ),
        )
        post_id = post["id"]

        results.extend(
            DistributionResult(
                requested_platform=target,
                adapter_platform=self.PLATFORM_MAP[target]["adapter"],
                status="queued",
                post_id=post_id,
            )
            for target in target_platforms
            if target in self.PLATFORM_MAP
        )
        return results
