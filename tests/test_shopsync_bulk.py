"""Tests for ShopSync CSV bulk import."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedUser
from app.main import app
from app.services.product_bomb import ProductBombResult
from app.services.product_image_analyzer import ProductAnalysis
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

_VALID_CSV = "name,price,category,image_url\n테스트 셔츠,29000,의류,https://img.test/1.jpg\n테스트 바지,39000,의류,https://img.test/2.jpg\n"
_NO_HEADER_CSV = "테스트 셔츠,29000,의류,https://img.test/1.jpg\n"
_MISSING_COL_CSV = "name,price,category\n셔츠,29000,의류\n"


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


def _make_bomb_result() -> ProductBombResult:
    from app.services.channel_renderers import (
        render_coupang,
        render_instagram,
        render_kakao,
        render_naver_blog,
        render_smart_store,
    )

    analysis = _make_analysis()
    imgs = ["https://img.test/1.jpg"]
    return ProductBombResult(
        analysis=analysis,
        smart_store=render_smart_store(analysis, 29000, imgs),
        coupang=render_coupang(analysis, 29000),
        instagram=render_instagram(analysis, 29000, imgs),
        naver_blog=render_naver_blog(analysis, 29000, imgs),
        kakao=render_kakao(analysis, 29000, imgs, "https://shop.test/p/1"),
    )


@pytest.fixture()
def fake_sb():
    return FakeSupabase()


@pytest.fixture()
def client(fake_sb):
    from app.api.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER

    mock_task = MagicMock()
    mock_task.delay = MagicMock()

    with (
        patch("app.core.db.get_supabase", return_value=fake_sb),
        patch("app.api.v1.shopsync.get_supabase", return_value=fake_sb),
        patch(
            "app.api.v1.shopsync.shopsync_bulk_import_task",
            mock_task,
            create=True,
        ) if False else
        patch(
            "app.workers.shopsync_bulk_worker.shopsync_bulk_import_task.delay",
            mock_task.delay,
        ),
    ):
        yield client_wrapper(TestClient(app), mock_task, fake_sb)
    app.dependency_overrides.clear()


class client_wrapper:
    """Wraps TestClient with access to mock_task and fake_sb."""

    def __init__(self, http: TestClient, mock_task: MagicMock, sb: FakeSupabase):
        self.http = http
        self.mock_task = mock_task
        self.sb = sb

    def post(self, *a, **kw):
        return self.http.post(*a, **kw)

    def get(self, *a, **kw):
        return self.http.get(*a, **kw)


def _upload(client, csv_text: str = _VALID_CSV, content_type: str = "text/csv"):
    return client.post(
        "/api/v1/shopsync/products/bulk-import",
        files={"file": ("products.csv", io.BytesIO(csv_text.encode()), content_type)},
    )


# ---------------------------------------------------------------------------
# 1. Normal CSV upload → 202 + job_id
# ---------------------------------------------------------------------------


def test_bulk_import_success(client):
    resp = _upload(client)
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["total_rows"] >= 2
    assert "/bulk-import/" in data["status_url"]
    assert len(client.sb.tables["shopsync_bulk_jobs"]) == 1


# ---------------------------------------------------------------------------
# 2. Invalid CSV format (missing header) → 400
# ---------------------------------------------------------------------------


def test_bulk_import_invalid_format(client):
    # CSV without proper column headers
    bad_csv = "col_a,col_b,col_c\nval1,val2,val3\n"
    resp = _upload(client, csv_text=bad_csv)
    assert resp.status_code == 400
    assert "Missing required columns" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Missing required column → 400
# ---------------------------------------------------------------------------


def test_bulk_import_missing_column(client):
    resp = _upload(client, csv_text=_MISSING_COL_CSV)
    assert resp.status_code == 400
    assert "image_url" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Empty file → 400
# ---------------------------------------------------------------------------


def test_bulk_import_empty_file(client):
    resp = _upload(client, csv_text="")
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Too many rows (>1000) → 413
# ---------------------------------------------------------------------------


def test_bulk_import_too_many_rows(client):
    header = "name,price,category,image_url\n"
    rows = "".join(f"item{i},1000,cat,https://img.test/{i}.jpg\n" for i in range(1002))
    resp = _upload(client, csv_text=header + rows)
    assert resp.status_code == 413
    assert "Too many rows" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Job status query → 200
# ---------------------------------------------------------------------------


def test_bulk_import_status(client):
    # Create a job first
    resp = _upload(client)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/api/v1/shopsync/products/bulk-import/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["id"] == job_id
    assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# 7. Worker partial failure (unit test of _run_bulk_import)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_partial_failure():
    fake_sb = FakeSupabase()
    fake_sb.table("shopsync_bulk_jobs").insert(
        {
            "id": "job-1",
            "user_id": "user-1",
            "status": "pending",
            "total_rows": 0,
            "succeeded": 0,
            "failed": 0,
            "results": [],
            "error": None,
        },
    ).execute()

    call_count = 0

    async def flaky_bomb(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Bomb failed for row 2")
        return _make_bomb_result()

    with (
        patch("app.workers.shopsync_bulk_worker.get_supabase", return_value=fake_sb),
        patch(
            "app.services.product_bomb.generate_product_bomb",
            side_effect=flaky_bomb,
        ),
    ):
        from app.workers.shopsync_bulk_worker import _run_bulk_import

        await _run_bulk_import("job-1", _VALID_CSV, "user-1")

    job = fake_sb.tables["shopsync_bulk_jobs"][0]
    assert job["status"] == "completed"
    assert job["succeeded"] == 1
    assert job["failed"] == 1
    assert len(fake_sb.tables["shopsync_products"]) == 1


# ---------------------------------------------------------------------------
# 8. No auth → 401
# ---------------------------------------------------------------------------


def test_bulk_import_no_auth(fake_sb):
    app.dependency_overrides.clear()
    with patch("app.core.db.get_supabase", return_value=fake_sb):
        c = TestClient(app)
        resp = c.post(
            "/api/v1/shopsync/products/bulk-import",
            files={"file": ("p.csv", io.BytesIO(b"x"), "text/csv")},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 9. IDOR on job status → 403
# ---------------------------------------------------------------------------


def test_bulk_import_status_idor(client):
    # Seed a job owned by a different user
    client.sb.table("shopsync_bulk_jobs").insert(
        {
            "id": "job-other",
            "user_id": "user-other",
            "status": "completed",
            "total_rows": 1,
            "succeeded": 1,
            "failed": 0,
            "results": [],
            "error": None,
        },
    ).execute()

    resp = client.get("/api/v1/shopsync/products/bulk-import/job-other")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 10. Completed job query shows results
# ---------------------------------------------------------------------------


def test_bulk_import_completed_query(client):
    client.sb.table("shopsync_bulk_jobs").insert(
        {
            "id": "job-done",
            "user_id": "user-1",
            "status": "completed",
            "total_rows": 3,
            "succeeded": 2,
            "failed": 1,
            "results": [
                {"index": 0, "status": "created", "product_id": "p1"},
                {"index": 1, "status": "created", "product_id": "p2"},
                {"index": 2, "status": "failed", "error": "price invalid"},
            ],
            "error": None,
        },
    ).execute()

    resp = client.get("/api/v1/shopsync/products/bulk-import/job-done")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["succeeded"] == 2
    assert data["failed"] == 1
    assert len(data["results"]) == 3
