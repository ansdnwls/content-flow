"""Tests for Viral Score Prediction API and service."""

from __future__ import annotations

from uuid import uuid4

import httpx
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from tests.fakes import FakeSupabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_user_and_key(fake_supabase: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users", {"id": user_id, "email": "predict@example.com", "plan": "free"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)
    return user_id, issued.raw_key


# ---------------------------------------------------------------------------
# Service — fallback tests (no Claude API key)
# ---------------------------------------------------------------------------

async def test_fallback_predict_basic(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    predictor = ViralPredictor()
    result = await predictor.predict_viral_score(
        title="10 Python Tips You Didn't Know!",
        description="Boost your Python skills with these hidden gems and tricks.",
        platform="youtube",
        tags=["python", "programming", "tips", "coding", "tutorial"],
    )

    assert 0 <= result.viral_score <= 100
    assert result.breakdown.curiosity >= 0
    assert result.breakdown.keyword_trend >= 0
    assert result.breakdown.emotional_intensity >= 0
    assert result.breakdown.platform_fit >= 0
    assert result.breakdown.total == result.viral_score
    assert len(result.suggestions) <= 3
    assert len(result.ab_variants) == 3


async def test_fallback_predict_short_title(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    predictor = ViralPredictor()
    result = await predictor.predict_viral_score(
        title="Hi",
        description="Short",
        platform="youtube",
        tags=[],
    )

    assert result.viral_score < 80
    assert any("short" in s.lower() or "tag" in s.lower() for s in result.suggestions)


async def test_fallback_predict_question_title(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    predictor = ViralPredictor()
    result = await predictor.predict_viral_score(
        title="Why Does Python Win Every Time?",
        description="A deep analysis of Python's dominance in programming.",
        platform="youtube",
        tags=["python", "programming", "analysis", "coding", "tech"],
    )

    assert result.breakdown.curiosity >= 15


async def test_fallback_predict_different_platforms(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    predictor = ViralPredictor()

    yt = await predictor.predict_viral_score(
        title="Ultimate Guide to Rust Programming",
        description="Learn Rust from scratch with practical examples " * 5,
        platform="youtube",
        tags=["rust", "programming"],
    )

    x_result = await predictor.predict_viral_score(
        title="Rust > Python. Fight me.",
        description="Hot take on systems programming.",
        platform="x",
        tags=["rust", "python"],
    )

    assert yt.viral_score != x_result.viral_score or yt.breakdown != x_result.breakdown


async def test_fallback_ab_test(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    predictor = ViralPredictor()
    result = await predictor.generate_ab_test(
        title="Python Tips",
        description="Learn Python tricks.",
        platform="youtube",
        tags=["python"],
    )

    assert len(result.title_variants) == 3
    assert len(result.description_variants) == 3
    assert len(result.tag_variants) == 3
    assert all(isinstance(tv, list) for tv in result.tag_variants)


# ---------------------------------------------------------------------------
# Service — Claude API mock tests
# ---------------------------------------------------------------------------

@respx.mock
async def test_predict_with_claude(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {
            "anthropic_api_key": "test-key",
            "anthropic_model": "claude-3-5-sonnet-latest",
            "anthropic_api_base_url": "https://api.anthropic.com/v1",
        })(),
    )

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"curiosity": 22, "keyword_trend": 18,'
                            ' "emotional_intensity": 20, "platform_fit": 23,'
                            ' "suggestions": ["Add numbers to title",'
                            ' "Use power words", "Add CTA"],'
                            ' "ab_variants": ['
                            '{"title": "Alt 1", "description": "Desc 1"},'
                            '{"title": "Alt 2", "description": "Desc 2"},'
                            '{"title": "Alt 3", "description": "Desc 3"}]}'
                        ),
                    },
                ],
            },
        ),
    )

    predictor = ViralPredictor()
    result = await predictor.predict_viral_score(
        title="10 Python Tips",
        description="Great tips for Python developers.",
        platform="youtube",
        tags=["python"],
    )

    assert result.viral_score == 22 + 18 + 20 + 23
    assert result.breakdown.curiosity == 22
    assert len(result.suggestions) == 3
    assert len(result.ab_variants) == 3


@respx.mock
async def test_predict_claude_error_falls_back(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {
            "anthropic_api_key": "test-key",
            "anthropic_model": "claude-3-5-sonnet-latest",
            "anthropic_api_base_url": "https://api.anthropic.com/v1",
        })(),
    )

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(500, text="Internal Server Error"),
    )

    predictor = ViralPredictor()
    result = await predictor.predict_viral_score(
        title="Test Title?",
        description="Test description for fallback.",
        platform="tiktok",
        tags=["test"],
    )

    assert 0 <= result.viral_score <= 100
    assert len(result.ab_variants) == 3


@respx.mock
async def test_ab_test_with_claude(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {
            "anthropic_api_key": "test-key",
            "anthropic_model": "claude-3-5-sonnet-latest",
            "anthropic_api_base_url": "https://api.anthropic.com/v1",
        })(),
    )

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"title_variants": ["T1", "T2", "T3"],'
                            ' "description_variants": ["D1", "D2", "D3"],'
                            ' "tag_variants": [["a","b"], ["c","d"], ["e","f"]]}'
                        ),
                    },
                ],
            },
        ),
    )

    predictor = ViralPredictor()
    result = await predictor.generate_ab_test(
        title="Original Title",
        description="Original description.",
        platform="instagram",
        tags=["test"],
    )

    assert result.title_variants == ["T1", "T2", "T3"]
    assert result.description_variants == ["D1", "D2", "D3"]
    assert len(result.tag_variants) == 3


# ---------------------------------------------------------------------------
# Service — edge cases
# ---------------------------------------------------------------------------

async def test_clamp_handles_out_of_range(monkeypatch) -> None:
    from app.services.viral_predictor import _clamp

    assert _clamp(30) == 25
    assert _clamp(-5) == 0
    assert _clamp(15) == 15


async def test_predict_unknown_platform_uses_youtube_defaults(monkeypatch) -> None:
    from app.services.viral_predictor import ViralPredictor

    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    predictor = ViralPredictor()
    result = await predictor.predict_viral_score(
        title="Test on unknown platform",
        description="Description for an unsupported platform.",
        platform="mastodon",
        tags=["test"],
    )

    assert 0 <= result.viral_score <= 100


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

async def test_api_viral_score(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    _user_id, raw_key = _setup_user_and_key(fake_supabase)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/predict/viral-score",
            json={
                "title": "Amazing Python Tricks!",
                "description": "10 tricks every developer should know.",
                "platform": "youtube",
                "tags": ["python", "tricks", "coding", "dev", "tutorial"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "viral_score" in body
        assert 0 <= body["viral_score"] <= 100
        assert "breakdown" in body
        assert "suggestions" in body
        assert "ab_variants" in body
        assert body["breakdown"]["curiosity"] >= 0
        assert body["breakdown"]["keyword_trend"] >= 0


async def test_api_viral_score_minimal(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    _user_id, raw_key = _setup_user_and_key(fake_supabase)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/predict/viral-score",
            json={
                "title": "Hi",
                "description": "Hello",
                "platform": "x",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["viral_score"] <= 100


async def test_api_ab_test(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    _user_id, raw_key = _setup_user_and_key(fake_supabase)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.viral_predictor.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/predict/ab-test",
            json={
                "title": "Python Tips",
                "description": "Learn Python.",
                "platform": "youtube",
                "tags": ["python"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["title_variants"]) == 3
        assert len(body["description_variants"]) == 3
        assert len(body["tag_variants"]) == 3


async def test_api_viral_score_unauthenticated(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            "/api/v1/predict/viral-score",
            json={
                "title": "Test",
                "description": "Test",
                "platform": "youtube",
            },
        )
        assert resp.status_code == 401
