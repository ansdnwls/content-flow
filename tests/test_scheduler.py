from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.workers.celery_app import celery_app
from tests.fakes import FakeSupabase


async def test_scheduler_enqueues_due_posts(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    due_time = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    future_time = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()

    fake_supabase.insert_row(
        "posts",
        {"id": "post-1", "owner_id": "owner-1", "status": "scheduled", "scheduled_for": due_time},
    )
    fake_supabase.insert_row(
        "posts",
        {
            "id": "post-2",
            "owner_id": "owner-1",
            "status": "scheduled",
            "scheduled_for": future_time,
        },
    )

    queued: list[tuple[str, str]] = []

    def fake_get_supabase() -> FakeSupabase:
        return fake_supabase

    class FakeTask:
        @staticmethod
        def delay(post_id: str, owner_id: str) -> None:
            queued.append((post_id, owner_id))

    monkeypatch.setattr("app.workers.scheduler.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.workers.scheduler.publish_post_task", FakeTask)

    from app.workers.scheduler import schedule_due_posts

    queued_ids = await schedule_due_posts()

    assert queued_ids == ["post-1"]
    assert queued == [("post-1", "owner-1")]
    assert fake_supabase.tables["posts"][0]["status"] == "pending"
    assert fake_supabase.tables["posts"][1]["status"] == "scheduled"


def test_celery_beat_schedule_registered() -> None:
    beat_schedule = celery_app.conf.beat_schedule
    entry = beat_schedule["schedule-due-posts-every-minute"]

    assert entry["task"] == "contentflow.schedule_due_posts"
    assert entry["schedule"] == 60.0


def test_oauth_refresh_beat_schedule_registered() -> None:
    beat_schedule = celery_app.conf.beat_schedule
    entry = beat_schedule["refresh-oauth-tokens-every-10-minutes"]

    assert entry["task"] == "contentflow.refresh_oauth_tokens"
    assert entry["schedule"] == 600.0
