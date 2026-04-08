"""Product Content Bomb — orchestrates image analysis + multi-channel rendering."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from app.services.channel_renderers.coupang_renderer import CoupangContent, render_coupang
from app.services.channel_renderers.instagram_renderer import InstagramContent, render_instagram
from app.services.channel_renderers.kakao_renderer import KakaoContent, render_kakao
from app.services.channel_renderers.naver_blog_renderer import NaverBlogContent, render_naver_blog
from app.services.channel_renderers.smart_store_renderer import (
    SmartStoreContent,
    render_smart_store,
)
from app.services.product_image_analyzer import ProductAnalysis, analyze_product

if TYPE_CHECKING:
    from app.services.shopsync_publisher import ShopsyncPublishResult


@dataclass(frozen=True)
class ProductBombResult:
    """Aggregated result from all channel renderers."""

    analysis: ProductAnalysis
    smart_store: SmartStoreContent | None = None
    coupang: CoupangContent | None = None
    instagram: InstagramContent | None = None
    naver_blog: NaverBlogContent | None = None
    kakao: KakaoContent | None = None
    errors: dict[str, str] = field(default_factory=dict)
    publish_result: ShopsyncPublishResult | None = None

    @property
    def channels_generated(self) -> list[str]:
        """List of channel names that were successfully generated."""
        result: list[str] = []
        if self.smart_store is not None:
            result.append("smart_store")
        if self.coupang is not None:
            result.append("coupang")
        if self.instagram is not None:
            result.append("instagram")
        if self.naver_blog is not None:
            result.append("naver_blog")
        if self.kakao is not None:
            result.append("kakao")
        return result


_ALL_PLATFORMS = frozenset(
    ["smart_store", "coupang", "instagram", "naver_blog", "kakao"]
)


async def generate_product_bomb(
    product_images: list[bytes],
    product_name: str,
    price: int,
    category: str = "",
    image_urls: list[str] | None = None,
    product_url: str = "",
    target_platforms: list[str] | None = None,
    auto_publish: bool = False,
    user_id: str = "",
    credentials: dict[str, dict[str, str]] | None = None,
) -> ProductBombResult:
    """
    Generate multi-channel content from product images.

    Args:
        product_images: Raw image bytes for Claude Vision analysis.
        product_name: Product name.
        price: Product price in KRW.
        category: Optional product category hint.
        image_urls: Public image URLs for embedding in rendered content.
        product_url: Link to the product page (used in Kakao CTA).
        target_platforms: Subset of platforms to generate for.
            Defaults to all 5 platforms.
        auto_publish: If True, publish rendered content to channels.
        user_id: Owner user ID (required when auto_publish=True).
        credentials: Per-channel credentials for publishing.

    Returns:
        ProductBombResult with analysis, per-channel content, and
        optional publish_result when auto_publish is True.
    """
    platforms = (
        _ALL_PLATFORMS
        if target_platforms is None
        else _ALL_PLATFORMS & set(target_platforms)
    )
    urls = image_urls or []

    # Step 1: Analyze product images
    analysis = await analyze_product(
        images=product_images,
        product_name=product_name,
        category=category,
    )

    # Step 2: Render each channel in parallel
    errors: dict[str, str] = {}
    results: dict[str, Any] = {}

    async def _render(name: str, fn: Any, *args: Any) -> None:
        try:
            results[name] = fn(*args)
        except Exception as exc:
            errors[name] = str(exc)

    tasks: list[asyncio.Task[None]] = []
    if "smart_store" in platforms:
        tasks.append(
            asyncio.create_task(_render("smart_store", render_smart_store, analysis, price, urls))
        )
    if "coupang" in platforms:
        tasks.append(
            asyncio.create_task(_render("coupang", render_coupang, analysis, price))
        )
    if "instagram" in platforms:
        tasks.append(
            asyncio.create_task(_render("instagram", render_instagram, analysis, price, urls))
        )
    if "naver_blog" in platforms:
        tasks.append(
            asyncio.create_task(_render("naver_blog", render_naver_blog, analysis, price, urls))
        )
    if "kakao" in platforms:
        tasks.append(
            asyncio.create_task(_render("kakao", render_kakao, analysis, price, urls, product_url))
        )

    if tasks:
        await asyncio.gather(*tasks)

    result = ProductBombResult(
        analysis=analysis,
        smart_store=results.get("smart_store"),
        coupang=results.get("coupang"),
        instagram=results.get("instagram"),
        naver_blog=results.get("naver_blog"),
        kakao=results.get("kakao"),
        errors=errors,
    )

    if auto_publish:
        from app.services.shopsync_publisher import ShopsyncPublisher

        publisher = ShopsyncPublisher()
        channels = list(platforms) if target_platforms is None else target_platforms
        pub_result = await publisher.publish(
            bomb_result=result,
            target_channels=channels,
            user_id=user_id,
            credentials=credentials,
        )
        result = replace(result, publish_result=pub_result)

    return result
