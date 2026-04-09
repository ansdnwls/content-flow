"""ShopSync publish orchestration — routes rendered content to platform adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.adapters.base import MediaSpec, PublishResult

if TYPE_CHECKING:
    from app.services.product_bomb import ProductBombResult


@dataclass(frozen=True)
class ChannelPublishResult:
    """Outcome of publishing to a single channel."""

    channel: str
    success: bool
    platform_post_id: str | None = None
    url: str | None = None
    error: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ShopsyncPublishResult:
    """Aggregated publish results across all channels."""

    results: list[ChannelPublishResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[str]:
        return [r.channel for r in self.results if r.success]

    @property
    def failed(self) -> list[str]:
        return [r.channel for r in self.results if not r.success]


def _build_smart_store_payload(
    bomb: ProductBombResult,
) -> tuple[str | None, list[MediaSpec], dict[str, Any]]:
    content = bomb.smart_store
    if content is None:
        return None, [], {}
    images = [
        MediaSpec(url=kw, media_type="image")
        for kw in content.keywords  # keywords used as placeholder
    ]
    options: dict[str, Any] = {
        "product_name": bomb.analysis.product_name,
        "price": 0,
        "stock_quantity": 0,
        "category_id": "",
        "detail_content": content.html,
    }
    return None, images, options


def _build_naver_blog_payload(
    bomb: ProductBombResult,
) -> tuple[str | None, list[MediaSpec], dict[str, Any]]:
    content = bomb.naver_blog
    if content is None:
        return None, [], {}
    return content.body_html, [], {"title": content.title, "tags": content.tags}


def _build_instagram_payload(
    bomb: ProductBombResult,
) -> tuple[str | None, list[MediaSpec], dict[str, Any]]:
    content = bomb.instagram
    if content is None:
        return None, [], {}
    media = [
        MediaSpec(url=s.image_url, media_type="image")
        for s in content.slides
        if s.image_url
    ]
    caption = content.caption
    if content.hashtags:
        caption = f"{caption}\n\n{content.hashtags}"
    return caption, media, {}


def _build_kakao_payload(
    bomb: ProductBombResult,
) -> tuple[str | None, list[MediaSpec], dict[str, Any]]:
    content = bomb.kakao
    if content is None:
        return None, [], {}
    media = (
        [MediaSpec(url=content.image_url, media_type="image")]
        if content.image_url
        else []
    )
    options: dict[str, Any] = {
        "title": content.title,
        "button_label": content.button_label,
        "button_url": content.button_url,
    }
    return content.message, media, options


def _build_coupang_payload(
    bomb: ProductBombResult,
) -> tuple[str | None, list[MediaSpec], dict[str, Any]]:
    content = bomb.coupang
    if content is None:
        return None, [], {}
    options: dict[str, Any] = {
        "product_name": content.title,
        "price": 0,
        "category_id": "",
    }
    return content.description, [], options


_PAYLOAD_BUILDERS = {
    "smart_store": _build_smart_store_payload,
    "naver_blog": _build_naver_blog_payload,
    "instagram": _build_instagram_payload,
    "kakao": _build_kakao_payload,
    "coupang": _build_coupang_payload,
}


def _get_adapter(channel: str) -> Any:
    """Lazily import and instantiate the adapter for *channel*."""
    if channel in ("smart_store", "naver_smart_store"):
        from app.adapters.naver_smart_store import NaverSmartStoreAdapter

        return NaverSmartStoreAdapter()
    if channel == "naver_blog":
        from app.adapters.naver_blog import NaverBlogAdapter

        return NaverBlogAdapter()
    if channel == "instagram":
        from app.adapters.instagram import InstagramAdapter

        return InstagramAdapter()
    if channel == "kakao":
        from app.adapters.kakao import KakaoAdapter

        return KakaoAdapter()
    if channel == "coupang":
        from app.adapters.coupang_wing import CoupangWingAdapter

        return CoupangWingAdapter()
    return None


class ShopsyncPublisher:
    """Publishes ProductBombResult to platform adapters with partial failure support."""

    async def publish(
        self,
        bomb_result: ProductBombResult,
        target_channels: list[str],
        user_id: str,
        credentials: dict[str, dict[str, str]] | None = None,
        dry_run: bool = False,
    ) -> ShopsyncPublishResult:
        """Publish rendered content to each target channel.

        Args:
            bomb_result: Rendered content from generate_product_bomb().
            target_channels: Channel names to publish to.
            user_id: Owner user ID.
            credentials: Per-channel credentials ``{channel: {key: val}}``.
            dry_run: If True, return payloads without calling adapters.

        Returns:
            ShopsyncPublishResult with per-channel outcomes.
        """
        creds = credentials or {}
        channel_results: list[ChannelPublishResult] = []

        for channel in target_channels:
            builder = _PAYLOAD_BUILDERS.get(channel)
            if builder is None:
                channel_results.append(
                    ChannelPublishResult(
                        channel=channel,
                        success=False,
                        error=f"Unsupported channel: {channel}",
                    )
                )
                continue

            # Check that content was actually generated for this channel
            generated = bomb_result.channels_generated
            if channel not in generated:
                channel_results.append(
                    ChannelPublishResult(
                        channel=channel,
                        success=False,
                        error=f"No content generated for {channel}",
                    )
                )
                continue

            text, media, options = builder(bomb_result)
            payload = {
                "text": text,
                "media": [{"url": m.url, "type": m.media_type} for m in media],
                "options": options,
            }

            if dry_run:
                channel_results.append(
                    ChannelPublishResult(
                        channel=channel,
                        success=True,
                        payload=payload,
                    )
                )
                continue

            adapter = _get_adapter(channel)
            if adapter is None:
                channel_results.append(
                    ChannelPublishResult(
                        channel=channel,
                        success=False,
                        error=f"No adapter for {channel}",
                    )
                )
                continue

            channel_creds = creds.get(channel, {})
            try:
                pub: PublishResult = await adapter.publish(
                    text=text,
                    media=media,
                    options=options,
                    credentials=channel_creds,
                )
                channel_results.append(
                    ChannelPublishResult(
                        channel=channel,
                        success=pub.success,
                        platform_post_id=pub.platform_post_id,
                        url=pub.url,
                        error=pub.error,
                    )
                )
            except Exception as exc:
                channel_results.append(
                    ChannelPublishResult(
                        channel=channel,
                        success=False,
                        error=str(exc),
                    )
                )

        return ShopsyncPublishResult(results=channel_results)
