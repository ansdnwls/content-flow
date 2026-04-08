"""Tests for ShopSync API endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedUser
from app.main import app
from app.services.product_bomb import ProductBombResult
from app.services.product_image_analyzer import ProductAnalysis
from app.services.shopsync_publisher import (
    ChannelPublishResult,
    ShopsyncPublishResult,
)
from tests.fakes import FakeSupabase

_TEST_USER = AuthenticatedUser(
    id="user-1",
    email="shop@example.com",
    plan="build",
    is_test_key=False,
)

_OTHER_USER = AuthenticatedUser(
    id="user-other",
    email="other@example.com",
    plan="build",
    is_test_key=False,
)


def _make_analysis() -> ProductAnalysis:
    return ProductAnalysis(
        product_name="테스트 셔츠",
        main_color="화이트",
        material="면 100%",
        style="캐주얼",
        target_audience="20-30대",
        use_cases=["데일리룩"],
        selling_points=["편안한 착용감"],
        suggested_keywords=["셔츠"],
        suggested_hashtags=["#셔츠"],
        description_summary="편안한 캐주얼 셔츠.",
    )


def _make_bomb_result(channels: list[str] | None = None) -> ProductBombResult:
    from app.services.channel_renderers import (
        render_coupang,
        render_instagram,
        render_kakao,
        render_naver_blog,
        render_smart_store,
    )

    analysis = _make_analysis()
    imgs = ["https://example.com/img.jpg"]
    all_channels = channels or [
        "smart_store", "coupang", "instagram", "naver_blog", "kakao",
    ]
    return ProductBombResult(
        analysis=analysis,
        smart_store=render_smart_store(analysis, 29000, imgs)
        if "smart_store" in all_channels else None,
        coupang=render_coupang(analysis, 29000)
        if "coupang" in all_channels else None,
        instagram=render_instagram(analysis, 29000, imgs)
        if "instagram" in all_channels else None,
        naver_blog=render_naver_blog(analysis, 29000, imgs)
        if "naver_blog" in all_channels else None,
        kakao=render_kakao(analysis, 29000, imgs, "https://shop.test/p/1")
        if "kakao" in all_channels else None,
    )


@pytest.fixture()
def fake_sb():
    return FakeSupabase()


@pytest.fixture()
def client(fake_sb):
    from app.api.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER
    with (
        patch("app.core.db.get_supabase", return_value=fake_sb),
        patch("app.api.v1.shopsync.get_supabase", return_value=fake_sb),
    ):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_product(fake_sb: FakeSupabase, user_id: str = "user-1") -> dict:
    """Insert a product row into the fake DB and return it."""
    row = {
        "id": "prod-1",
        "user_id": user_id,
        "product_name": "테스트 셔츠",
        "price": 29000,
        "category": "의류",
        "image_urls": ["https://example.com/img.jpg"],
        "target_platforms": ["smart_store", "coupang"],
        "channels_generated": ["smart_store", "coupang"],
        "status": "generated",
    }
    fake_sb.table("shopsync_products").insert(row).execute()
    return row


# ---------------------------------------------------------------------------
# 1. No auth header → 401
# ---------------------------------------------------------------------------


def test_no_auth_returns_401(fake_sb):
    app.dependency_overrides.clear()
    with patch("app.core.db.get_supabase", return_value=fake_sb):
        c = TestClient(app)
        resp = c.get("/api/v1/shopsync/products")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. POST /products → 201 (create product + bomb)
# ---------------------------------------------------------------------------


def test_create_product(client, fake_sb):
    bomb = _make_bomb_result(["smart_store", "coupang"])
    mock_bomb = AsyncMock(return_value=bomb)

    with patch("app.services.product_bomb.generate_product_bomb", mock_bomb):
        resp = client.post(
            "/api/v1/shopsync/products",
            json={
                "product_name": "테스트 셔츠",
                "price": 29000,
                "category": "의류",
                "image_urls": ["https://example.com/img.jpg"],
                "target_platforms": ["smart_store", "coupang"],
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["product_name"] == "테스트 셔츠"
    assert data["price"] == 29000
    assert "smart_store" in data["channels_generated"]
    assert "coupang" in data["channels_generated"]
    assert len(fake_sb.tables["shopsync_products"]) == 1


# ---------------------------------------------------------------------------
# 3. GET /products → list with pagination
# ---------------------------------------------------------------------------


def test_list_products(client, fake_sb):
    _seed_product(fake_sb, user_id="user-1")
    resp = client.get("/api/v1/shopsync/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert len(data["data"]) >= 1


# ---------------------------------------------------------------------------
# 4. GET /products/{id} → detail
# ---------------------------------------------------------------------------


def test_get_product_detail(client, fake_sb):
    _seed_product(fake_sb)
    resp = client.get("/api/v1/shopsync/products/prod-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "테스트 셔츠"
    assert data["price"] == 29000


# ---------------------------------------------------------------------------
# 5. GET /products/{id} IDOR → 404 (different user's product)
# ---------------------------------------------------------------------------


def test_get_product_idor_returns_404(client, fake_sb):
    _seed_product(fake_sb, user_id="user-other")
    resp = client.get("/api/v1/shopsync/products/prod-1")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. POST /products/{id}/publish → success
# ---------------------------------------------------------------------------


def test_publish_product_success(client, fake_sb):
    _seed_product(fake_sb)
    bomb = _make_bomb_result(["smart_store", "coupang"])

    pub_result = ShopsyncPublishResult(
        results=[
            ChannelPublishResult(
                channel="smart_store", success=True,
                platform_post_id="ss_123",
            ),
            ChannelPublishResult(
                channel="coupang", success=True,
                platform_post_id="cp_123",
            ),
        ],
    )

    mock_bomb = AsyncMock(return_value=bomb)
    mock_publish = AsyncMock(return_value=pub_result)

    with (
        patch("app.services.product_bomb.generate_product_bomb", mock_bomb),
        patch.object(
            type(mock_publish), "publish",
            new=mock_publish,
            create=True,
        ) if False else
        patch(
            "app.services.shopsync_publisher.ShopsyncPublisher.publish",
            mock_publish,
        ),
    ):
        resp = client.post(
            "/api/v1/shopsync/products/prod-1/publish",
            json={"target_channels": ["smart_store", "coupang"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["succeeded"]) == 2
    assert len(data["failed"]) == 0
    # Status should be updated to published
    row = fake_sb.tables["shopsync_products"][0]
    assert row["status"] == "published"


# ---------------------------------------------------------------------------
# 7. POST /products/{id}/publish → partial failure
# ---------------------------------------------------------------------------


def test_publish_partial_failure(client, fake_sb):
    _seed_product(fake_sb)
    bomb = _make_bomb_result(["smart_store", "coupang"])

    pub_result = ShopsyncPublishResult(
        results=[
            ChannelPublishResult(
                channel="smart_store", success=False,
                error="Token expired",
            ),
            ChannelPublishResult(
                channel="coupang", success=True,
                platform_post_id="cp_456",
            ),
        ],
    )

    mock_bomb = AsyncMock(return_value=bomb)
    mock_publish = AsyncMock(return_value=pub_result)

    with (
        patch("app.services.product_bomb.generate_product_bomb", mock_bomb),
        patch(
            "app.services.shopsync_publisher.ShopsyncPublisher.publish",
            mock_publish,
        ),
    ):
        resp = client.post(
            "/api/v1/shopsync/products/prod-1/publish",
            json={"target_channels": ["smart_store", "coupang"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "smart_store" in data["failed"]
    assert "coupang" in data["succeeded"]


# ---------------------------------------------------------------------------
# 8. POST /products/{id}/publish → dry_run (no status change)
# ---------------------------------------------------------------------------


def test_publish_dry_run(client, fake_sb):
    _seed_product(fake_sb)
    bomb = _make_bomb_result(["smart_store"])

    pub_result = ShopsyncPublishResult(
        results=[
            ChannelPublishResult(
                channel="smart_store", success=True,
                payload={"text": None, "media": [], "options": {}},
            ),
        ],
    )

    mock_bomb = AsyncMock(return_value=bomb)
    mock_publish = AsyncMock(return_value=pub_result)

    with (
        patch("app.services.product_bomb.generate_product_bomb", mock_bomb),
        patch(
            "app.services.shopsync_publisher.ShopsyncPublisher.publish",
            mock_publish,
        ),
    ):
        resp = client.post(
            "/api/v1/shopsync/products/prod-1/publish",
            json={"target_channels": ["smart_store"], "dry_run": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    # Status should NOT change on dry_run
    row = fake_sb.tables["shopsync_products"][0]
    assert row["status"] == "generated"


# ---------------------------------------------------------------------------
# 9. DELETE /products/{id} → 204
# ---------------------------------------------------------------------------


def test_delete_product(client, fake_sb):
    _seed_product(fake_sb)
    assert len(fake_sb.tables["shopsync_products"]) == 1
    resp = client.delete("/api/v1/shopsync/products/prod-1")
    assert resp.status_code == 204
    assert len(fake_sb.tables["shopsync_products"]) == 0


# ---------------------------------------------------------------------------
# 10. DELETE /products/{id} not found → 404
# ---------------------------------------------------------------------------


def test_delete_product_not_found(client, fake_sb):
    resp = client.delete("/api/v1/shopsync/products/nonexistent")
    assert resp.status_code == 404
