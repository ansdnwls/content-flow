"""Tests for video template system."""

from __future__ import annotations

from uuid import uuid4

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from app.services.video_templates import (
    BUILTIN_TEMPLATES,
    db_row_to_template,
    get_template,
    list_builtin_templates,
)
from tests.fakes import FakeSupabase


def _setup_user_and_key(fake: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row("users", {"id": user_id, "email": "vid@example.com", "plan": "build"})
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


# ---------- Unit tests for video_templates service ----------

def test_builtin_templates_count() -> None:
    assert len(BUILTIN_TEMPLATES) == 5


def test_get_template_existing() -> None:
    tmpl = get_template("news_brief")
    assert tmpl is not None
    assert tmpl.name == "News Brief"
    assert tmpl.duration_seconds == 30
    assert len(tmpl.scenes) == 4


def test_get_template_nonexistent() -> None:
    assert get_template("nonexistent") is None


def test_list_builtin_templates() -> None:
    templates = list_builtin_templates()
    assert len(templates) == 5
    ids = {t["id"] for t in templates}
    assert ids == {"news_brief", "quote_card", "listicle", "story", "tutorial"}


def test_template_to_dict() -> None:
    tmpl = get_template("quote_card")
    d = tmpl.to_dict()
    assert d["id"] == "quote_card"
    assert d["voice_tone"] == "calm"
    assert d["bgm_mood"] == "inspirational"
    assert len(d["scenes"]) == 3
    assert d["is_builtin"] is True


def test_template_to_yt_factory_params() -> None:
    tmpl = get_template("tutorial")
    params = tmpl.to_yt_factory_params()
    assert params["template_id"] == "tutorial"
    assert params["duration_seconds"] == 120
    assert len(params["scenes"]) == 6
    assert params["voice_tone"] == "instructional"


def test_db_row_to_template() -> None:
    row = {
        "id": "custom-1",
        "name": "My Template",
        "description": "Custom template",
        "duration_seconds": 45,
        "scenes": [
            {"name": "intro", "duration_seconds": 10, "description": "Intro scene."},
            {"name": "body", "duration_seconds": 35, "description": "Body scene."},
        ],
        "caption_style": "subtitle_bottom",
        "voice_tone": "friendly",
        "bgm_mood": "chill",
    }
    tmpl = db_row_to_template(row)
    assert tmpl.id == "custom-1"
    assert tmpl.is_builtin is False
    assert len(tmpl.scenes) == 2
    assert tmpl.scenes[0].name == "intro"


# ---------- API integration tests ----------

async def test_list_templates_returns_builtins(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup_user_and_key(fake)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/videos/templates")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 5
    ids = {t["id"] for t in body["data"]}
    assert "news_brief" in ids
    assert "tutorial" in ids


async def test_get_builtin_template(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup_user_and_key(fake)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/videos/templates/story")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "story"
    assert body["duration_seconds"] == 90
    assert len(body["scenes"]) == 5


async def test_get_template_not_found(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup_user_and_key(fake)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/videos/templates/nonexistent")

    assert resp.status_code == 404


async def test_create_custom_template(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup_user_and_key(fake)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/videos/templates",
            json={
                "name": "Product Demo",
                "description": "Quick product showcase.",
                "duration_seconds": 45,
                "scenes": [
                    {"name": "intro", "duration_seconds": 8, "description": "Product intro."},
                    {"name": "demo", "duration_seconds": 30, "description": "Feature walkthrough."},
                    {"name": "cta", "duration_seconds": 7, "description": "Buy now CTA."},
                ],
                "caption_style": "bold_white",
                "voice_tone": "friendly",
                "bgm_mood": "upbeat",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Product Demo"
    assert body["is_builtin"] is False
    assert len(body["scenes"]) == 3
    assert len(fake.tables["video_templates"]) == 1


async def test_template_list_cache_is_invalidated_on_create(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup_user_and_key(fake)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def fake_cache_redis():
        return redis

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.cache.get_redis", fake_cache_redis)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        first = await client.get("/api/v1/videos/templates")
        create = await client.post(
            "/api/v1/videos/templates",
            json={
                "name": "Cache Bust",
                "description": "Invalidate template list cache.",
                "duration_seconds": 20,
                "scenes": [
                    {"name": "intro", "duration_seconds": 10, "description": "A"},
                    {"name": "cta", "duration_seconds": 10, "description": "B"},
                ],
            },
        )
        second = await client.get("/api/v1/videos/templates")

    assert first.status_code == 200
    assert create.status_code == 201
    assert second.status_code == 200
    assert second.json()["total"] == first.json()["total"] + 1
    ids = {item["id"] for item in second.json()["data"]}
    assert create.json()["id"] in ids


async def test_create_template_conflict_with_builtin(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup_user_and_key(fake)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/videos/templates",
            json={
                "name": "News Brief",
                "duration_seconds": 30,
                "scenes": [
                    {"name": "s1", "duration_seconds": 30, "description": "Scene."},
                ],
            },
        )

    assert resp.status_code == 409


async def test_generate_video_with_template(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake)

    queued: list[tuple[str, str]] = []

    class FakeTask:
        @staticmethod
        def delay(video_id: str, owner_id: str) -> None:
            queued.append((video_id, owner_id))

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.videos.generate_video_task", FakeTask)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/videos/generate",
            json={
                "topic": "Python tricks",
                "mode": "educational",
                "template": "listicle",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["template"] == "listicle"
    assert body["status"] == "queued"
    assert len(queued) == 1
