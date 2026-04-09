"""Tests for ShopSync publish orchestration."""
from __future__ import annotations

import pytest

from app.adapters.base import PublishResult
from app.services.product_bomb import ProductBombResult
from app.services.product_image_analyzer import ProductAnalysis
from app.services.shopsync_publisher import ShopsyncPublisher

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_analysis() -> ProductAnalysis:
    return ProductAnalysis(
        product_name="테스트 셔츠",
        main_color="화이트",
        material="면 100%",
        style="캐주얼",
        target_audience="20-30대",
        use_cases=["데일리룩"],
        selling_points=["편안한 착용감", "세탁 용이"],
        suggested_keywords=["셔츠", "캐주얼"],
        suggested_hashtags=["#셔츠", "#데일리"],
        description_summary="편안한 캐주얼 셔츠.",
    )


@pytest.fixture()
def bomb_result() -> ProductBombResult:
    """ProductBombResult with all 5 channels rendered."""
    from app.services.channel_renderers import (
        render_coupang,
        render_instagram,
        render_kakao,
        render_naver_blog,
        render_smart_store,
    )

    analysis = _make_analysis()
    imgs = ["https://example.com/img.jpg"]
    return ProductBombResult(
        analysis=analysis,
        smart_store=render_smart_store(analysis, 29000, imgs),
        coupang=render_coupang(analysis, 29000),
        instagram=render_instagram(analysis, 29000, imgs),
        naver_blog=render_naver_blog(analysis, 29000, imgs),
        kakao=render_kakao(analysis, 29000, imgs, "https://shop.test/p/1"),
    )


def _patch_adapters(monkeypatch, fail_channels: set[str] | None = None):
    """Patch all adapter publish() methods to return success or failure."""
    failures = fail_channels or set()

    async def _mock_publish(self, text, media, options, credentials):
        channel = self.platform_name
        if channel in failures:
            return PublishResult(
                success=False, error=f"{channel} publish failed"
            )
        return PublishResult(
            success=True,
            platform_post_id=f"mock_{channel}_123",
            url=f"https://{channel}.test/mock_123",
        )

    monkeypatch.setattr(
        "app.adapters.naver_smart_store.NaverSmartStoreAdapter.publish",
        _mock_publish,
    )
    monkeypatch.setattr(
        "app.adapters.naver_blog.NaverBlogAdapter.publish",
        _mock_publish,
    )
    monkeypatch.setattr(
        "app.adapters.instagram.InstagramAdapter.publish",
        _mock_publish,
    )
    monkeypatch.setattr(
        "app.adapters.kakao.KakaoAdapter.publish",
        _mock_publish,
    )
    monkeypatch.setattr(
        "app.adapters.coupang_wing.CoupangWingAdapter.publish",
        _mock_publish,
    )


# ---------------------------------------------------------------------------
# 1. All channels succeed
# ---------------------------------------------------------------------------

async def test_publish_all_channels_success(
    monkeypatch, bomb_result: ProductBombResult,
) -> None:
    _patch_adapters(monkeypatch)
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=["smart_store", "naver_blog", "instagram", "kakao", "coupang"],
        user_id="user-1",
    )
    assert len(result.succeeded) == 5
    assert len(result.failed) == 0


# ---------------------------------------------------------------------------
# 2. Partial failure — smart_store fails, others succeed
# ---------------------------------------------------------------------------

async def test_publish_partial_failure(
    monkeypatch, bomb_result: ProductBombResult,
) -> None:
    _patch_adapters(monkeypatch, fail_channels={"naver_smart_store"})
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=["smart_store", "coupang", "instagram"],
        user_id="user-1",
    )
    assert "smart_store" in result.failed
    assert "coupang" in result.succeeded
    assert "instagram" in result.succeeded


# ---------------------------------------------------------------------------
# 3. Dry run — no actual calls, payloads returned
# ---------------------------------------------------------------------------

async def test_publish_dry_run(bomb_result: ProductBombResult) -> None:
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=["smart_store", "coupang"],
        user_id="user-1",
        dry_run=True,
    )
    assert len(result.results) == 2
    for r in result.results:
        assert r.success is True
        assert r.payload is not None
        assert "text" in r.payload
        assert "options" in r.payload


# ---------------------------------------------------------------------------
# 4. Unsupported channel — graceful skip
# ---------------------------------------------------------------------------

async def test_publish_unsupported_channel(
    bomb_result: ProductBombResult,
) -> None:
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=["eleven_street"],
        user_id="user-1",
    )
    assert len(result.failed) == 1
    assert result.results[0].error is not None
    assert "Unsupported" in (result.results[0].error or "")


# ---------------------------------------------------------------------------
# 5. Smart store with no token — unauthorized
# ---------------------------------------------------------------------------

async def test_smart_store_no_token(
    monkeypatch, bomb_result: ProductBombResult,
) -> None:
    # Don't patch — use real adapter which returns error on missing token
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=["smart_store"],
        user_id="user-1",
        credentials={"smart_store": {}},
    )
    assert len(result.failed) == 1
    assert "access_token" in (result.results[0].error or "").lower()


# ---------------------------------------------------------------------------
# 6. Coupang mock — returns {mock: True}
# ---------------------------------------------------------------------------

async def test_coupang_mock_publish(
    monkeypatch,
    bomb_result: ProductBombResult,
) -> None:
    _patch_adapters(monkeypatch)
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=["coupang"],
        user_id="user-1",
    )
    assert len(result.succeeded) == 1
    assert result.results[0].platform_post_id is not None
    assert "mock_coupang_wing_" in (result.results[0].platform_post_id or "")


# ---------------------------------------------------------------------------
# 7. product_bomb + auto_publish integration
# ---------------------------------------------------------------------------

async def test_product_bomb_auto_publish(monkeypatch) -> None:
    analysis = _make_analysis()

    async def mock_analyze(images, product_name="", category=""):
        return analysis

    monkeypatch.setattr(
        "app.services.product_bomb.analyze_product", mock_analyze,
    )
    _patch_adapters(monkeypatch)

    from app.services.product_bomb import generate_product_bomb

    result = await generate_product_bomb(
        product_images=[b"fake"],
        product_name="테스트 셔츠",
        price=29000,
        image_urls=["https://example.com/img.jpg"],
        auto_publish=True,
        user_id="user-1",
    )

    assert result.publish_result is not None
    assert len(result.publish_result.succeeded) == 5
    assert len(result.publish_result.failed) == 0


# ---------------------------------------------------------------------------
# 8. auto_publish=False — no publish_result (regression)
# ---------------------------------------------------------------------------

async def test_product_bomb_no_auto_publish(monkeypatch) -> None:
    analysis = _make_analysis()

    async def mock_analyze(images, product_name="", category=""):
        return analysis

    monkeypatch.setattr(
        "app.services.product_bomb.analyze_product", mock_analyze,
    )

    from app.services.product_bomb import generate_product_bomb

    result = await generate_product_bomb(
        product_images=[b"fake"],
        product_name="테스트 셔츠",
        price=29000,
    )

    assert result.publish_result is None
    assert len(result.channels_generated) == 5


# ---------------------------------------------------------------------------
# 9. Empty target_channels — no publish
# ---------------------------------------------------------------------------

async def test_publish_empty_channels(
    bomb_result: ProductBombResult,
) -> None:
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=[],
        user_id="user-1",
    )
    assert len(result.results) == 0
    assert result.succeeded == []
    assert result.failed == []


# ---------------------------------------------------------------------------
# 10. Single channel only — only that channel called
# ---------------------------------------------------------------------------

async def test_publish_single_channel(
    monkeypatch, bomb_result: ProductBombResult,
) -> None:
    _patch_adapters(monkeypatch)
    publisher = ShopsyncPublisher()
    result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=["kakao"],
        user_id="user-1",
    )
    assert len(result.results) == 1
    assert result.results[0].channel == "kakao"
    assert result.results[0].success is True
