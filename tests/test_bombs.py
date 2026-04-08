from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from tests.fakes import FakeSupabase


async def test_bombs_create_get_publish(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row("users", {"id": user_id, "email": "owner@example.com", "plan": "free"})

    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)
    ready_bomb_id = str(uuid4())
    fake_supabase.insert_row(
        "bombs",
        {
            "id": ready_bomb_id,
            "user_id": user_id,
            "topic": "Ready topic",
            "status": "ready",
            "platform_contents": {"x": {"title": "Ready topic", "publish_status": "draft"}},
        },
    )

    queued_transforms: list[tuple[str, str]] = []
    queued_publishes: list[tuple[str, str]] = []

    def fake_get_supabase() -> FakeSupabase:
        return fake_supabase

    class FakeTransformTask:
        @staticmethod
        def delay(bomb_id: str, owner_id: str) -> None:
            queued_transforms.append((bomb_id, owner_id))

    class FakePublishTask:
        @staticmethod
        def delay(bomb_id: str, owner_id: str) -> None:
            queued_publishes.append((bomb_id, owner_id))

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.bombs.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.bombs.transform_bomb_task", FakeTransformTask)
    monkeypatch.setattr("app.api.v1.bombs.publish_bomb_task", FakePublishTask)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": issued.raw_key},
    ) as client:
        create_response = await client.post("/api/v1/bombs", json={"topic": "Driver safety myths"})
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["status"] == "queued"
        assert created["topic"] == "Driver safety myths"
        assert len(queued_transforms) == 1

        get_response = await client.get(f"/api/v1/bombs/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["topic"] == "Driver safety myths"

        publish_response = await client.post(f"/api/v1/bombs/{ready_bomb_id}/publish")
        assert publish_response.status_code == 200
        assert len(queued_publishes) == 1


async def test_content_transformer_fallback_contains_platform_rules() -> None:
    from app.services.content_transformer import ContentTransformer

    transformer = ContentTransformer()
    transformed = await transformer.transform_topic("DUI 3-strike laws")

    assert "youtube" in transformed
    assert "tiktok" in transformed
    assert transformed["x"]["publish_status"] == "draft"
    assert "seo" in transformed["blog"]["body"].lower()


async def test_bomb_worker_transform_and_publish(monkeypatch) -> None:
    from app.workers.bomb_worker import run_bomb_publish, run_bomb_transform

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row("users", {"id": user_id, "email": "owner@example.com", "plan": "free"})
    fake_supabase.insert_row(
        "bombs",
        {
            "id": "bomb-1",
            "user_id": user_id,
            "topic": "DUI 3-strike laws",
            "status": "queued",
            "platform_contents": {},
        },
    )
    dispatched: list[tuple[str, str, dict]] = []

    def fake_get_supabase() -> FakeSupabase:
        return fake_supabase

    async def fake_transform(_: str) -> dict:
        return {"youtube": {"title": "Explainer", "publish_status": "draft"}}

    async def fake_dispatch(owner_id: str, event: str, payload: dict) -> None:
        dispatched.append((owner_id, event, payload))

    monkeypatch.setattr("app.workers.bomb_worker.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.workers.bomb_worker.dispatch_event", fake_dispatch)
    monkeypatch.setattr(
        "app.workers.bomb_worker.ContentTransformer",
        type("FakeTransformer", (), {"transform_topic": staticmethod(fake_transform)}),
    )

    transformed = await run_bomb_transform("bomb-1", user_id)
    assert transformed["status"] == "ready"
    assert transformed["platform_contents"]["youtube"]["publish_status"] == "draft"

    published = await run_bomb_publish("bomb-1", user_id)
    assert published["status"] == "published"
    assert published["platform_contents"]["youtube"]["publish_status"] == "published"
    assert dispatched[0][1] == "post.published"
