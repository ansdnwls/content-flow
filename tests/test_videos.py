from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


async def test_videos_create_and_fetch(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row("users", {"id": user_id, "email": "owner@example.com", "plan": "free"})

    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)

    queued: list[tuple[str, str]] = []

    def fake_get_supabase() -> FakeSupabase:
        return fake_supabase

    class FakeTask:
        @staticmethod
        def delay(video_id: str, owner_id: str) -> None:
            queued.append((video_id, owner_id))

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.videos.generate_video_task", FakeTask)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": issued.raw_key},
    ) as client:
        create_response = await client.post(
            "/api/v1/videos/generate",
            json={
                "topic": "DUI 3-strike laws",
                "mode": "legal",
                "language": "ko",
                "format": "shorts",
                "style": "realistic",
                "auto_publish": {"enabled": True, "platforms": ["youtube"]},
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["status"] == "queued"
        assert created["topic"] == "DUI 3-strike laws"
        assert len(queued) == 1

        video_id = created["id"]

        get_response = await client.get(f"/api/v1/videos/{video_id}")
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["id"] == video_id
        assert fetched["mode"] == "legal"
