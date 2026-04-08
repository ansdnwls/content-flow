from __future__ import annotations

from types import SimpleNamespace

import respx
from httpx import Response

from app.workers.video_worker import run_video_generation
from tests.fakes import FakeSupabase


async def test_video_worker_generates_and_auto_publishes(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    owner_id = "user-1"
    fake_supabase.insert_row(
        "users",
        {"id": owner_id, "email": "owner@example.com", "plan": "build"},
    )
    fake_supabase.insert_row(
        "social_accounts",
        {
            "id": "account-youtube",
            "owner_id": owner_id,
            "platform": "youtube",
            "handle": "@channel",
            "display_name": "Channel",
            "metadata": {},
        },
    )
    fake_supabase.insert_row(
        "video_jobs",
        {
            "id": "video-1",
            "owner_id": owner_id,
            "topic": "DUI 3-strike laws",
            "mode": "legal",
            "language": "ko",
            "format": "shorts",
            "style": "realistic",
            "status": "queued",
            "auto_publish": {"enabled": True, "platforms": ["youtube"]},
        },
    )

    queued_posts: list[tuple[str, str]] = []
    dispatched: list[tuple[str, str, dict]] = []

    def fake_get_supabase() -> FakeSupabase:
        return fake_supabase

    class FakeTask:
        @staticmethod
        def delay(post_id: str, job_owner_id: str) -> None:
            queued_posts.append((post_id, job_owner_id))

    async def fake_dispatch(owner: str, event: str, payload: dict) -> None:
        dispatched.append((owner, event, payload))

    settings = SimpleNamespace(
        yt_factory_base_url="http://yt-factory.local",
        yt_factory_api_key="secret",
        yt_factory_timeout_seconds=30,
        yt_factory_poll_interval_seconds=0,
    )

    monkeypatch.setattr("app.workers.video_worker.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.publish_post_task", FakeTask)
    monkeypatch.setattr("app.workers.video_worker.dispatch_event", fake_dispatch)
    monkeypatch.setattr("app.workers.video_worker.get_settings", lambda: settings)

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://yt-factory.local/api/v1/pipelines/run")
        route.mock(
            return_value=Response(
                200,
                json={
                    "job_id": "provider-123",
                    "status": "completed",
                    "output_url": "https://cdn.example.com/video-1.mp4",
                },
            ),
        )
        result = await run_video_generation("video-1", owner_id)

    assert result["status"] == "completed"
    assert result["provider_job_id"] == "provider-123"
    assert result["output_url"] == "https://cdn.example.com/video-1.mp4"
    assert queued_posts and queued_posts[0][1] == owner_id
    assert len(fake_supabase.tables["posts"]) == 1
    assert fake_supabase.tables["post_deliveries"][0]["social_account_id"] == "account-youtube"
    assert dispatched[0][1] == "video.completed"
    assert result["auto_publish"]["post_id"] == fake_supabase.tables["posts"][0]["id"]
