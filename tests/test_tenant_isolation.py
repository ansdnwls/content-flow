"""Tests for multi-tenant isolation across all resource types."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedUser
from app.core.tenant_isolation import (
    TenantViolationError,
    require_owner,
    require_owner_or_workspace,
    scoped_query,
)
from app.main import app
from tests.fakes import FakeSupabase

_USER_A = AuthenticatedUser(
    id="user-a",
    email="a@example.com",
    plan="build",
    is_test_key=False,
    workspace_id="ws-shared",
)

_USER_B = AuthenticatedUser(
    id="user-b",
    email="b@example.com",
    plan="build",
    is_test_key=False,
    workspace_id="ws-other",
)

_USER_WS_SHARED = AuthenticatedUser(
    id="user-ws",
    email="ws@example.com",
    plan="build",
    is_test_key=False,
    workspace_id="ws-shared",
)


@pytest.fixture()
def fake_sb():
    return FakeSupabase()


def _client_as(fake_sb: FakeSupabase, user: AuthenticatedUser) -> TestClient:
    from app.api.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _cleanup():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unit tests for tenant_isolation helpers
# ---------------------------------------------------------------------------


# 1. require_owner — valid owner
def test_require_owner_passes():
    row = {"id": "r1", "user_id": "user-a", "data": "ok"}
    result = require_owner(
        row, "user-a", resource="Product", resource_id="r1",
    )
    assert result["data"] == "ok"


# 2. require_owner — wrong owner raises
def test_require_owner_wrong_user():
    row = {"id": "r1", "user_id": "user-a"}
    with pytest.raises(TenantViolationError) as exc_info:
        require_owner(row, "user-b", resource="Product", resource_id="r1")
    assert "user-b" not in str(exc_info.value)
    assert "Product" in str(exc_info.value)


# 3. require_owner — None row raises
def test_require_owner_none_row():
    with pytest.raises(TenantViolationError):
        require_owner(None, "user-a", resource="Product", resource_id="r1")


# 4. require_owner_or_workspace — owner match
def test_require_owner_or_workspace_owner():
    row = {"id": "r1", "owner_id": "user-a", "workspace_id": "ws-1"}
    result = require_owner_or_workspace(
        row, "user-a", "ws-other",
        resource="Post", resource_id="r1",
    )
    assert result["id"] == "r1"


# 5. require_owner_or_workspace — workspace match
def test_require_owner_or_workspace_shared():
    row = {"id": "r1", "owner_id": "user-a", "workspace_id": "ws-shared"}
    result = require_owner_or_workspace(
        row, "user-ws", "ws-shared",
        resource="Post", resource_id="r1",
    )
    assert result["id"] == "r1"


# 6. require_owner_or_workspace — no match raises
def test_require_owner_or_workspace_denied():
    row = {"id": "r1", "owner_id": "user-a", "workspace_id": "ws-1"}
    with pytest.raises(TenantViolationError):
        require_owner_or_workspace(
            row, "user-b", "ws-other",
            resource="Post", resource_id="r1",
        )


# 7. scoped_query applies user_id filter
def test_scoped_query_user_filter(fake_sb):
    fake_sb.table("shopsync_products").insert(
        {"id": "p1", "user_id": "user-a", "product_name": "A"},
    ).execute()
    fake_sb.table("shopsync_products").insert(
        {"id": "p2", "user_id": "user-b", "product_name": "B"},
    ).execute()

    rows = scoped_query(
        fake_sb, "shopsync_products", "user-a",
    ).execute().data
    assert len(rows) == 1
    assert rows[0]["user_id"] == "user-a"


# ---------------------------------------------------------------------------
# Integration tests — IDOR across resource types
# ---------------------------------------------------------------------------


# 8. ShopSync product — other user → 404
def test_shopsync_product_idor(fake_sb):
    fake_sb.table("shopsync_products").insert(
        {
            "id": "prod-a",
            "user_id": "user-a",
            "product_name": "A의 상품",
            "price": 10000,
            "status": "generated",
        },
    ).execute()

    with patch("app.core.db.get_supabase", return_value=fake_sb), \
         patch("app.api.v1.shopsync.get_supabase", return_value=fake_sb):
        c = _client_as(fake_sb, _USER_B)
        resp = c.get("/api/v1/shopsync/products/prod-a")
    _cleanup()
    assert resp.status_code == 404


# 9. ShopSync bulk job — other user → 403
def test_shopsync_bulk_job_idor(fake_sb):
    fake_sb.table("shopsync_bulk_jobs").insert(
        {
            "id": "job-a",
            "user_id": "user-a",
            "status": "completed",
            "total_rows": 1,
            "succeeded": 1,
            "failed": 0,
            "results": [],
            "error": None,
        },
    ).execute()

    with patch("app.core.db.get_supabase", return_value=fake_sb), \
         patch("app.api.v1.shopsync.get_supabase", return_value=fake_sb):
        c = _client_as(fake_sb, _USER_B)
        resp = c.get("/api/v1/shopsync/products/bulk-import/job-a")
    _cleanup()
    assert resp.status_code == 403


# 10. ShopSync delete — other user → 404
def test_shopsync_delete_idor(fake_sb):
    fake_sb.table("shopsync_products").insert(
        {
            "id": "prod-a",
            "user_id": "user-a",
            "product_name": "A의 상품",
            "price": 10000,
            "status": "generated",
        },
    ).execute()

    with patch("app.core.db.get_supabase", return_value=fake_sb), \
         patch("app.api.v1.shopsync.get_supabase", return_value=fake_sb):
        c = _client_as(fake_sb, _USER_B)
        resp = c.delete("/api/v1/shopsync/products/prod-a")
    _cleanup()
    assert resp.status_code == 404
    # Verify product still exists
    assert len(fake_sb.tables["shopsync_products"]) == 1


# 11. ShopSync analytics — other user sees empty
def test_shopsync_analytics_idor(fake_sb):
    fake_sb.table("shopsync_products").insert(
        {
            "id": "prod-a",
            "user_id": "user-a",
            "product_name": "A",
            "price": 10000,
            "channels_generated": ["smart_store"],
            "status": "published",
        },
    ).execute()

    with patch("app.core.db.get_supabase", return_value=fake_sb), \
         patch("app.api.v1.shopsync.get_supabase", return_value=fake_sb):
        c = _client_as(fake_sb, _USER_B)
        resp = c.get("/api/v1/shopsync/analytics/overview")
    _cleanup()
    assert resp.status_code == 200
    assert resp.json()["this_month_products"] == 0


# 12. No auth header → 401
def test_no_auth_returns_401(fake_sb):
    app.dependency_overrides.clear()
    with patch("app.core.db.get_supabase", return_value=fake_sb):
        c = TestClient(app)
        resp = c.get("/api/v1/shopsync/products")
    assert resp.status_code == 401


# 13. Wrong workspace_id in scoped_query
def test_scoped_query_workspace_filter(fake_sb):
    fake_sb.table("posts").insert(
        {"id": "p1", "owner_id": "user-a", "workspace_id": "ws-1", "status": "pending"},
    ).execute()
    fake_sb.table("posts").insert(
        {"id": "p2", "owner_id": "user-a", "workspace_id": "ws-2", "status": "pending"},
    ).execute()

    rows = scoped_query(
        fake_sb, "posts", "user-b",
        workspace_id="ws-1", owner_field="owner_id",
    ).execute().data
    assert len(rows) == 1
    assert rows[0]["workspace_id"] == "ws-1"


# 14. require_owner with custom owner_field
def test_require_owner_custom_field():
    row = {"id": "v1", "owner_id": "user-a"}
    result = require_owner(
        row, "user-a",
        resource="Video", resource_id="v1", owner_field="owner_id",
    )
    assert result["id"] == "v1"

    with pytest.raises(TenantViolationError):
        require_owner(
            row, "user-b",
            resource="Video", resource_id="v1", owner_field="owner_id",
        )


# 15. ShopSync list — only own products visible
def test_shopsync_list_isolation(fake_sb):
    for i, uid in enumerate(["user-a", "user-a", "user-b"]):
        fake_sb.table("shopsync_products").insert(
            {
                "id": f"prod-{i}",
                "user_id": uid,
                "product_name": f"상품 {i}",
                "price": 10000,
                "status": "generated",
            },
        ).execute()

    with patch("app.core.db.get_supabase", return_value=fake_sb), \
         patch("app.api.v1.shopsync.get_supabase", return_value=fake_sb):
        c = _client_as(fake_sb, _USER_A)
        resp = c.get("/api/v1/shopsync/products")
    _cleanup()
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for item in data["data"]:
        assert item["user_id"] == "user-a"
