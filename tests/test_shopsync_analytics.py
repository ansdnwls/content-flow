"""Tests for ShopSync analytics endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedUser
from app.main import app
from tests.fakes import FakeSupabase

_TEST_USER = AuthenticatedUser(
    id="user-1",
    email="shop@example.com",
    plan="build",
    is_test_key=False,
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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _days_ago(n: int) -> str:
    return (datetime.now(UTC) - timedelta(days=n)).isoformat()


def _seed_products(fake_sb: FakeSupabase, count: int = 3, **overrides) -> None:
    """Insert *count* products into the fake DB."""
    defaults = {
        "user_id": "user-1",
        "product_name": "셔츠",
        "price": 29000,
        "category": "의류",
        "image_urls": [],
        "target_platforms": ["smart_store", "coupang"],
        "channels_generated": ["smart_store", "coupang"],
        "status": "published",
    }
    defaults.update(overrides)
    for i in range(count):
        row = {
            **defaults,
            "id": f"prod-{i}",
            "product_name": f"{defaults['product_name']} {i}",
            "created_at": overrides.get("created_at", _now_iso()),
        }
        fake_sb.table("shopsync_products").insert(row).execute()


# ---------------------------------------------------------------------------
# 1. Overview — normal data
# ---------------------------------------------------------------------------


def test_overview_with_data(client, fake_sb):
    _seed_products(fake_sb, count=3)
    resp = client.get("/api/v1/shopsync/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["this_month_products"] == 3
    assert data["channels_published"] == 6  # 3 products * 2 channels
    assert data["time_saved_hours"] > 0


# ---------------------------------------------------------------------------
# 2. Overview — empty data (0 products)
# ---------------------------------------------------------------------------


def test_overview_empty(client):
    resp = client.get("/api/v1/shopsync/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["this_month_products"] == 0
    assert data["channels_published"] == 0
    assert data["time_saved_hours"] == 0
    assert data["products_change_pct"] is None


# ---------------------------------------------------------------------------
# 3. By-channel aggregation
# ---------------------------------------------------------------------------


def test_by_channel(client, fake_sb):
    _seed_products(
        fake_sb, count=2,
        channels_generated=["smart_store", "coupang", "instagram"],
        status="published",
    )
    _seed_products(
        fake_sb, count=1,
        channels_generated=["smart_store"],
        status="generated",
    )
    resp = client.get("/api/v1/shopsync/analytics/by-channel")
    assert resp.status_code == 200
    data = resp.json()
    channels = {c["channel"]: c for c in data["channels"]}
    assert "smart_store" in channels
    assert channels["smart_store"]["total"] == 3
    assert channels["smart_store"]["published"] == 2
    assert channels["coupang"]["total"] == 2


# ---------------------------------------------------------------------------
# 4. Top products sorted by channel count
# ---------------------------------------------------------------------------


def test_top_products_sorted(client, fake_sb):
    fake_sb.table("shopsync_products").insert(
        {
            "id": "p-5ch",
            "user_id": "user-1",
            "product_name": "풀 채널 상품",
            "price": 50000,
            "channels_generated": [
                "smart_store", "coupang", "instagram", "naver_blog", "kakao",
            ],
            "status": "published",
            "created_at": _now_iso(),
        },
    ).execute()
    fake_sb.table("shopsync_products").insert(
        {
            "id": "p-2ch",
            "user_id": "user-1",
            "product_name": "2채널 상품",
            "price": 20000,
            "channels_generated": ["smart_store", "coupang"],
            "status": "generated",
            "created_at": _now_iso(),
        },
    ).execute()

    resp = client.get("/api/v1/shopsync/analytics/top-products")
    assert resp.status_code == 200
    products = resp.json()["products"]
    assert len(products) == 2
    assert products[0]["id"] == "p-5ch"
    assert products[0]["channel_count"] == 5
    assert products[1]["channel_count"] == 2


# ---------------------------------------------------------------------------
# 5. Time-saved calculation accuracy
# ---------------------------------------------------------------------------


def test_time_saved_calculation(client, fake_sb):
    _seed_products(fake_sb, count=10)
    resp = client.get("/api/v1/shopsync/analytics/time-saved?period=daily&days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_products"] == 10
    # 10 products * 5.833... hours saved each
    expected = round(10 * (6.0 - 10.0 / 60.0), 1)
    assert data["total_saved_hours"] == expected
    assert len(data["series"]) >= 1
    # Each series entry should have the right keys
    entry = data["series"][0]
    assert "manual_hours" in entry
    assert "shopsync_hours" in entry
    assert "saved_hours" in entry


# ---------------------------------------------------------------------------
# 6. No auth → 401
# ---------------------------------------------------------------------------


def test_analytics_no_auth(fake_sb):
    app.dependency_overrides.clear()
    with patch("app.core.db.get_supabase", return_value=fake_sb):
        c = TestClient(app)
        resp = c.get("/api/v1/shopsync/analytics/overview")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 7. IDOR — other user's products not visible
# ---------------------------------------------------------------------------


def test_overview_idor(client, fake_sb):
    # Seed products for a different user
    _seed_products(fake_sb, count=5, user_id="user-other")
    resp = client.get("/api/v1/shopsync/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["this_month_products"] == 0  # user-1 sees nothing


# ---------------------------------------------------------------------------
# 8. Date range filter on by-channel
# ---------------------------------------------------------------------------


def test_by_channel_date_filter(client, fake_sb):
    # Products from 60 days ago should not appear in current month
    old_date = _days_ago(60)
    _seed_products(fake_sb, count=3, created_at=old_date)
    _seed_products(fake_sb, count=2, created_at=_now_iso())

    resp = client.get("/api/v1/shopsync/analytics/by-channel")
    assert resp.status_code == 200
    channels = resp.json()["channels"]
    total = sum(c["total"] for c in channels)
    # Only current month products (2 * 2 channels = 4)
    assert total == 4


# ---------------------------------------------------------------------------
# 9. Top-products pagination (limit)
# ---------------------------------------------------------------------------


def test_top_products_limit(client, fake_sb):
    _seed_products(fake_sb, count=15)
    resp = client.get("/api/v1/shopsync/analytics/top-products?limit=5")
    assert resp.status_code == 200
    assert len(resp.json()["products"]) == 5


# ---------------------------------------------------------------------------
# 10. Time-saved invalid period → 400
# ---------------------------------------------------------------------------


def test_time_saved_invalid_period(client):
    resp = client.get("/api/v1/shopsync/analytics/time-saved?period=hourly")
    assert resp.status_code == 400
    assert "period" in resp.json()["detail"]
