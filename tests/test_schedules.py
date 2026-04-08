"""Tests for Scheduling Engine: service, API, and worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from tests.fakes import FakeSupabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_user_and_key(fake_supabase: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users", {"id": user_id, "email": "scheduler@example.com", "plan": "free"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)
    return user_id, issued.raw_key


def _insert_schedule(
    fake_supabase: FakeSupabase,
    user_id: str,
    *,
    schedule_id: str | None = None,
    platform: str = "youtube",
    recurrence: str = "daily",
    is_active: bool = True,
    next_run_at: str | None = None,
) -> dict:
    row = {
        "id": schedule_id or str(uuid4()),
        "user_id": user_id,
        "post_id": None,
        "platform": platform,
        "tz": "UTC",
        "recurrence": recurrence,
        "cron_expression": None,
        "next_run_at": next_run_at or datetime.now(UTC).isoformat(),
        "is_active": is_active,
    }
    return fake_supabase.insert_row("schedules", row)


# ---------------------------------------------------------------------------
# Service — timezone utilities
# ---------------------------------------------------------------------------

async def test_resolve_timezone() -> None:
    from app.services.scheduler_service import resolve_timezone

    kst = resolve_timezone("KST")
    assert kst.utcoffset(None) == timedelta(hours=9)

    utc = resolve_timezone("UTC")
    assert utc.utcoffset(None) == timedelta(0)

    unknown = resolve_timezone("UNKNOWN")
    assert unknown.utcoffset(None) == timedelta(0)


async def test_to_utc() -> None:
    from app.services.scheduler_service import to_utc

    naive = datetime(2026, 4, 7, 14, 0, 0)
    utc_time = to_utc(naive, "KST")
    assert utc_time.hour == 5  # 14:00 KST = 05:00 UTC


async def test_compute_next_run_daily() -> None:
    from app.services.scheduler_service import compute_next_run

    base = datetime(2026, 4, 7, 10, 0, 0, tzinfo=UTC)
    nxt = compute_next_run("daily", "UTC", base_time=base)
    assert nxt > base
    assert (nxt - base).days == 1


async def test_compute_next_run_weekly() -> None:
    from app.services.scheduler_service import compute_next_run

    base = datetime(2026, 4, 7, 10, 0, 0, tzinfo=UTC)
    nxt = compute_next_run("weekly", "UTC", base_time=base)
    assert nxt > base
    assert (nxt - base).days == 7


async def test_compute_next_run_once() -> None:
    from app.services.scheduler_service import compute_next_run

    base = datetime(2026, 4, 7, 10, 0, 0, tzinfo=UTC)
    nxt = compute_next_run("once", "UTC", base_time=base)
    assert nxt > base


async def test_compute_next_run_custom_cron() -> None:
    from app.services.scheduler_service import compute_next_run

    base = datetime(2026, 4, 6, 10, 0, 0, tzinfo=UTC)  # Monday
    nxt = compute_next_run("custom", "UTC", base_time=base, cron_expression="14:00 wed,fri")
    assert nxt > base
    assert nxt.hour == 14
    assert nxt.weekday() in (2, 4)  # Wed or Fri


# ---------------------------------------------------------------------------
# Service — recommendations
# ---------------------------------------------------------------------------

async def test_recommend_times_youtube() -> None:
    from app.services.scheduler_service import SchedulerService

    recs = SchedulerService.recommend_times(["youtube"], "UTC")
    assert len(recs) == 1
    assert recs[0].platform == "youtube"
    assert len(recs[0].recommended_times) > 0
    assert "2-4 PM" in recs[0].description


async def test_recommend_times_multiple() -> None:
    from app.services.scheduler_service import SchedulerService

    recs = SchedulerService.recommend_times(["youtube", "tiktok", "linkedin"], "KST")
    platforms = [r.platform for r in recs]
    assert "youtube" in platforms
    assert "tiktok" in platforms
    assert "linkedin" in platforms


async def test_recommend_times_unknown_platform() -> None:
    from app.services.scheduler_service import SchedulerService

    recs = SchedulerService.recommend_times(["mastodon"], "UTC")
    assert len(recs) == 1
    assert "No specific peak data" in recs[0].description


# ---------------------------------------------------------------------------
# Service — CRUD
# ---------------------------------------------------------------------------

async def test_create_schedule(monkeypatch) -> None:
    from app.services.scheduler_service import SchedulerService

    fake_supabase = FakeSupabase()
    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    service = SchedulerService()
    schedule = await service.create_schedule(
        user_id="u1", platform="youtube", recurrence="daily", tz="KST",
    )

    assert schedule["platform"] == "youtube"
    assert schedule["recurrence"] == "daily"
    assert schedule["tz"] == "KST"
    assert schedule["is_active"] is True
    assert "next_run_at" in schedule


async def test_list_schedules(monkeypatch) -> None:
    from app.services.scheduler_service import SchedulerService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    _insert_schedule(fake_supabase, user_id)
    _insert_schedule(fake_supabase, user_id, platform="tiktok")

    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    service = SchedulerService()
    data, total = await service.list_schedules(user_id)
    assert total == 2
    assert len(data) == 2


async def test_delete_schedule(monkeypatch) -> None:
    from app.services.scheduler_service import SchedulerService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    schedule = _insert_schedule(fake_supabase, user_id)

    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    service = SchedulerService()
    deleted = await service.delete_schedule(schedule["id"], user_id)
    assert deleted is True

    # Verify it's inactive now
    row = fake_supabase.tables["schedules"][0]
    assert row["is_active"] is False


async def test_delete_schedule_not_found(monkeypatch) -> None:
    from app.services.scheduler_service import SchedulerService

    fake_supabase = FakeSupabase()
    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    service = SchedulerService()
    deleted = await service.delete_schedule(str(uuid4()), "u1")
    assert deleted is False


async def test_get_due_schedules(monkeypatch) -> None:
    from app.services.scheduler_service import SchedulerService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    _insert_schedule(fake_supabase, user_id, next_run_at=past)
    _insert_schedule(fake_supabase, user_id, platform="tiktok", next_run_at=future)

    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    service = SchedulerService()
    due = await service.get_due_schedules()
    assert len(due) == 1
    assert due[0]["platform"] == "youtube"


async def test_advance_schedule_daily(monkeypatch) -> None:
    from app.services.scheduler_service import SchedulerService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    schedule = _insert_schedule(fake_supabase, user_id, recurrence="daily")

    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    service = SchedulerService()
    advanced = await service.advance_schedule(schedule["id"], schedule)
    assert advanced is not None
    assert advanced["next_run_at"] != schedule["next_run_at"]


async def test_advance_schedule_once_deactivates(monkeypatch) -> None:
    from app.services.scheduler_service import SchedulerService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    schedule = _insert_schedule(fake_supabase, user_id, recurrence="once")

    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    service = SchedulerService()
    result = await service.advance_schedule(schedule["id"], schedule)
    assert result is None
    assert fake_supabase.tables["schedules"][0]["is_active"] is False


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

async def test_schedule_worker_runs_due(monkeypatch) -> None:
    from app.workers.schedule_worker import run_due_schedules

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    _insert_schedule(fake_supabase, user_id, recurrence="daily", next_run_at=past)

    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    result = await run_due_schedules()
    assert result["executed"] == 1
    assert result["scanned"] == 1


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

async def test_api_create_schedule(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    _user_id, raw_key = _setup_user_and_key(fake_supabase)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/schedules",
            json={
                "platform": "youtube",
                "recurrence": "daily",
                "tz": "KST",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["platform"] == "youtube"
        assert body["tz"] == "KST"
        assert body["is_active"] is True


async def test_api_list_schedules(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    _insert_schedule(fake_supabase, user_id)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/schedules")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1


async def test_api_delete_schedule(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    schedule = _insert_schedule(fake_supabase, user_id)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.scheduler_service.get_supabase", lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.delete(f"/api/v1/schedules/{schedule['id']}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Delete again → 404
        resp2 = await client.delete(f"/api/v1/schedules/{uuid4()}")
        assert resp2.status_code == 404


async def test_api_recommend_times(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    _user_id, raw_key = _setup_user_and_key(fake_supabase)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(
            "/api/v1/schedules/recommend",
            params={"platforms": "youtube,tiktok", "tz": "KST"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        platforms = [r["platform"] for r in body]
        assert "youtube" in platforms
        assert "tiktok" in platforms


async def test_api_schedule_unauthenticated(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            "/api/v1/schedules",
            json={"platform": "youtube", "recurrence": "daily"},
        )
        assert resp.status_code == 401
