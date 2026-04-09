"""Tests for ShopSync Product Content Bomb engine and channel renderers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.channel_renderers.coupang_renderer import render_coupang
from app.services.channel_renderers.instagram_renderer import render_instagram
from app.services.channel_renderers.kakao_renderer import render_kakao
from app.services.channel_renderers.naver_blog_renderer import render_naver_blog
from app.services.channel_renderers.smart_store_renderer import render_smart_store
from app.services.product_image_analyzer import ProductAnalysis

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_analysis() -> ProductAnalysis:
    return ProductAnalysis(
        product_name="코튼 오버핏 티셔츠",
        main_color="네이비",
        material="면 100%",
        style="캐주얼",
        target_audience="20-30대 남녀",
        use_cases=["데일리룩", "캠퍼스룩", "여행"],
        selling_points=["오버핏 실루엣", "부드러운 면 소재", "사계절 착용 가능"],
        suggested_keywords=["오버핏티", "면티셔츠", "데일리룩"],
        suggested_hashtags=["#오버핏", "#데일리룩", "#면티"],
        description_summary=(
            "부드러운 면 소재의 오버핏 티셔츠. "
            "데일리룩부터 캠퍼스룩까지 다양하게 활용 가능합니다."
        ),
    )


SAMPLE_IMAGES = [
    "https://example.com/img/front.jpg",
    "https://example.com/img/back.jpg",
    "https://example.com/img/detail.jpg",
]

SAMPLE_PRICE = 29000


# ---------------------------------------------------------------------------
# SmartStore renderer
# ---------------------------------------------------------------------------

def test_smart_store_renderer_html(sample_analysis: ProductAnalysis) -> None:
    result = render_smart_store(sample_analysis, SAMPLE_PRICE, SAMPLE_IMAGES)
    assert "코튼 오버핏 티셔츠" in result.html
    assert "29,000" in result.html
    assert "네이비" in result.html
    assert result.seo_title
    assert result.seo_description
    assert len(result.keywords) > 0


def test_smart_store_renderer_images_in_html(sample_analysis: ProductAnalysis) -> None:
    result = render_smart_store(sample_analysis, SAMPLE_PRICE, SAMPLE_IMAGES)
    for url in SAMPLE_IMAGES:
        assert url in result.html


def test_smart_store_renderer_empty_images(sample_analysis: ProductAnalysis) -> None:
    result = render_smart_store(sample_analysis, SAMPLE_PRICE, [])
    assert "코튼 오버핏 티셔츠" in result.html


# ---------------------------------------------------------------------------
# Coupang renderer
# ---------------------------------------------------------------------------

def test_coupang_renderer_content(sample_analysis: ProductAnalysis) -> None:
    result = render_coupang(sample_analysis, SAMPLE_PRICE)
    assert "코튼 오버핏 티셔츠" in result.title
    assert "네이비" in result.title
    assert len(result.bullet_points) >= 3
    assert "20-30대 남녀" in result.description
    assert len(result.keywords) > 0


# ---------------------------------------------------------------------------
# Instagram renderer
# ---------------------------------------------------------------------------

def test_instagram_renderer_slides(sample_analysis: ProductAnalysis) -> None:
    result = render_instagram(sample_analysis, SAMPLE_PRICE, SAMPLE_IMAGES)
    assert len(result.slides) >= 3
    assert result.slides[0].overlay_text == "코튼 오버핏 티셔츠"
    assert "29,000" in result.slides[-1].overlay_text


def test_instagram_renderer_caption(sample_analysis: ProductAnalysis) -> None:
    result = render_instagram(sample_analysis, SAMPLE_PRICE, SAMPLE_IMAGES)
    assert "29,000" in result.caption
    assert result.hashtags


def test_instagram_renderer_empty_images(sample_analysis: ProductAnalysis) -> None:
    result = render_instagram(sample_analysis, SAMPLE_PRICE, [])
    assert result.caption


# ---------------------------------------------------------------------------
# Naver Blog renderer
# ---------------------------------------------------------------------------

def test_naver_blog_renderer_html(sample_analysis: ProductAnalysis) -> None:
    result = render_naver_blog(sample_analysis, SAMPLE_PRICE, SAMPLE_IMAGES)
    assert "코튼 오버핏 티셔츠" in result.title
    assert "<h2>" in result.body_html
    assert "29,000" in result.body_html
    assert SAMPLE_IMAGES[0] in result.body_html
    assert len(result.tags) > 0
    assert result.meta_description


def test_naver_blog_renderer_empty_images(sample_analysis: ProductAnalysis) -> None:
    result = render_naver_blog(sample_analysis, SAMPLE_PRICE, [])
    assert "코튼 오버핏 티셔츠" in result.body_html


# ---------------------------------------------------------------------------
# Kakao renderer
# ---------------------------------------------------------------------------

def test_kakao_renderer_message(sample_analysis: ProductAnalysis) -> None:
    result = render_kakao(
        sample_analysis, SAMPLE_PRICE, SAMPLE_IMAGES, product_url="https://shop.example.com/p/1"
    )
    assert "코튼 오버핏 티셔츠" in result.title
    assert "29,000" in result.message
    assert result.button_url == "https://shop.example.com/p/1"
    assert result.image_url == SAMPLE_IMAGES[0]
    assert result.button_label


def test_kakao_renderer_empty_images(sample_analysis: ProductAnalysis) -> None:
    result = render_kakao(sample_analysis, SAMPLE_PRICE, [])
    assert result.image_url == ""


# ---------------------------------------------------------------------------
# ProductBomb orchestrator (mocked image analysis)
# ---------------------------------------------------------------------------

async def test_product_bomb_all_channels(monkeypatch, sample_analysis: ProductAnalysis) -> None:
    """Full pipeline with mocked image analyzer generates all 5 channels."""

    async def mock_analyze(images, product_name="", category=""):
        return sample_analysis

    monkeypatch.setattr(
        "app.services.product_bomb.analyze_product",
        mock_analyze,
    )

    from app.services.product_bomb import generate_product_bomb

    result = await generate_product_bomb(
        product_images=[b"fake-jpg-bytes"],
        product_name="코튼 오버핏 티셔츠",
        price=SAMPLE_PRICE,
        image_urls=SAMPLE_IMAGES,
        product_url="https://shop.example.com/p/1",
    )

    assert result.analysis == sample_analysis
    assert result.smart_store is not None
    assert result.coupang is not None
    assert result.instagram is not None
    assert result.naver_blog is not None
    assert result.kakao is not None
    assert len(result.errors) == 0
    assert sorted(result.channels_generated) == [
        "coupang", "instagram", "kakao", "naver_blog", "smart_store",
    ]


async def test_product_bomb_subset_platforms(monkeypatch, sample_analysis: ProductAnalysis) -> None:
    """Only requested platforms are generated."""

    async def mock_analyze(images, product_name="", category=""):
        return sample_analysis

    monkeypatch.setattr(
        "app.services.product_bomb.analyze_product",
        mock_analyze,
    )

    from app.services.product_bomb import generate_product_bomb

    result = await generate_product_bomb(
        product_images=[b"fake-jpg-bytes"],
        product_name="코튼 오버핏 티셔츠",
        price=SAMPLE_PRICE,
        image_urls=SAMPLE_IMAGES,
        target_platforms=["coupang", "kakao"],
    )

    assert result.coupang is not None
    assert result.kakao is not None
    assert result.smart_store is None
    assert result.instagram is None
    assert result.naver_blog is None
    assert result.channels_generated == ["coupang", "kakao"]


async def test_product_bomb_no_images_urls(monkeypatch, sample_analysis: ProductAnalysis) -> None:
    """Pipeline works even without image URLs (only raw bytes for analysis)."""

    async def mock_analyze(images, product_name="", category=""):
        return sample_analysis

    monkeypatch.setattr(
        "app.services.product_bomb.analyze_product",
        mock_analyze,
    )

    from app.services.product_bomb import generate_product_bomb

    result = await generate_product_bomb(
        product_images=[b"fake-jpg-bytes"],
        product_name="코튼 오버핏 티셔츠",
        price=SAMPLE_PRICE,
    )

    assert result.analysis is not None
    assert len(result.channels_generated) == 5
    assert len(result.errors) == 0


# ---------------------------------------------------------------------------
# Naver SmartStore adapter
# ---------------------------------------------------------------------------

async def test_naver_smart_store_publish_missing_token() -> None:
    """Publish fails gracefully when access_token is missing."""
    from app.adapters.naver_smart_store import NaverSmartStoreAdapter

    adapter = NaverSmartStoreAdapter()
    result = await adapter.publish(
        text=None,
        media=[],
        options={"product_name": "Test"},
        credentials={},
    )
    assert result.success is False
    assert "access_token" in (result.error or "").lower()


async def test_naver_smart_store_validate_no_token() -> None:
    """Validation returns False when no token provided."""
    from app.adapters.naver_smart_store import NaverSmartStoreAdapter

    adapter = NaverSmartStoreAdapter()
    assert await adapter.validate_credentials({}) is False


# ---------------------------------------------------------------------------
# Coupang WING mock adapter
# ---------------------------------------------------------------------------

class _FakeCoupangResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = "ok"

    def json(self) -> dict:
        return self._payload


class _FakeCoupangClient:
    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(self, *_args, **_kwargs) -> _FakeCoupangResponse:
        return _FakeCoupangResponse(200, {"data": "coupang_mock_123", "mock": True})

    async def get(self, *_args, **_kwargs) -> _FakeCoupangResponse:
        return _FakeCoupangResponse(200, {"mock": True})

    async def delete(self, *_args, **_kwargs) -> _FakeCoupangResponse:
        return _FakeCoupangResponse(204, {})


def _coupang_credentials() -> dict[str, str]:
    return {
        "access_key": "access-key",
        "secret_key": "secret-key",
        "vendor_id": "vendor-123",
    }


async def test_coupang_mock_publish(monkeypatch) -> None:
    """Mock adapter returns success with mocked HTTP responses."""
    from app.adapters.coupang_wing import CoupangWingAdapter

    monkeypatch.setattr(
        "app.adapters.coupang_wing.httpx",
        SimpleNamespace(AsyncClient=_FakeCoupangClient),
    )
    adapter = CoupangWingAdapter()
    result = await adapter.publish(
        text=None,
        media=[],
        options={"product_name": "테스트 상품", "price": 10000, "category_id": "1001"},
        credentials=_coupang_credentials(),
    )
    assert result.success is True
    assert result.platform_post_id is not None
    assert "coupang_mock_" in result.platform_post_id
    assert result.raw_response is not None
    assert result.raw_response["mock"] is True


async def test_coupang_mock_publish_missing_name() -> None:
    """Mock adapter fails if product_name is missing."""
    from app.adapters.coupang_wing import CoupangWingAdapter

    adapter = CoupangWingAdapter()
    result = await adapter.publish(
        text=None,
        media=[],
        options={},
        credentials={},
    )
    assert result.success is False


async def test_coupang_mock_validate(monkeypatch) -> None:
    """Mock adapter validates successfully with mocked HTTP responses."""
    from app.adapters.coupang_wing import CoupangWingAdapter

    monkeypatch.setattr(
        "app.adapters.coupang_wing.httpx",
        SimpleNamespace(AsyncClient=_FakeCoupangClient),
    )
    adapter = CoupangWingAdapter()
    assert await adapter.validate_credentials(_coupang_credentials()) is True


async def test_coupang_mock_delete(monkeypatch) -> None:
    """Mock adapter delete succeeds with mocked HTTP responses."""
    from app.adapters.coupang_wing import CoupangWingAdapter

    monkeypatch.setattr(
        "app.adapters.coupang_wing.httpx",
        SimpleNamespace(AsyncClient=_FakeCoupangClient),
    )
    adapter = CoupangWingAdapter()
    assert await adapter.delete("any-id", _coupang_credentials()) is True
