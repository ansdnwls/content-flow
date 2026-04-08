"""Tests for YtBoost channel tone learning."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeSupabase

FAKE_TONE_ANALYSIS = {
    "average_length": 45,
    "emoji_frequency": 0.2,
    "greeting_patterns": ["감사합니다!", "안녕하세요"],
    "formality": "casual",
    "representative_phrases": [
        "좋은 질문이에요",
        "도움이 됐다니 기뻐요",
        "구독 감사합니다",
        "다음 영상도 기대해주세요",
        "화이팅!",
    ],
    "style_summary": "Warm casual Korean with gratitude expressions",
}


def _make_reply_comments(fake: FakeSupabase, user_id: str, count: int) -> None:
    """Insert reply comments into the fake DB."""
    for i in range(count):
        fake.insert_row(
            "comments",
            {
                "user_id": user_id,
                "platform": "youtube",
                "platform_post_id": f"vid_{i}",
                "platform_comment_id": f"c_{i}",
                "author_id": f"a_{i}",
                "author_name": f"User{i}",
                "text": f"Great video {i}",
                "ai_reply": f"Thanks for watching! Reply {i}",
                "reply_status": "replied",
            },
        )


def _make_channel(fake: FakeSupabase, user_id: str) -> str:
    """Insert a channel subscription and return its id."""
    row = fake.insert_row(
        "ytboost_subscriptions",
        {
            "user_id": user_id,
            "youtube_channel_id": "UC_test_channel",
            "channel_name": "Test Channel",
            "auto_distribute": False,
            "target_platforms": [],
            "auto_comment_mode": "review",
            "subscribed_at": datetime.now(UTC).isoformat(),
        },
    )
    return row["id"]


async def _mock_claude_response(*args, **kwargs) -> MagicMock:
    """Simulate a successful Claude API response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": json.dumps(FAKE_TONE_ANALYSIS)}],
    }
    return mock_resp


@pytest.fixture()
def fake_db():
    return FakeSupabase()


@pytest.fixture()
def user_id():
    return str(uuid4())


async def test_tone_learning_success(monkeypatch, fake_db, user_id) -> None:
    """Tone learning succeeds with Claude mock and stores profile."""
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    _make_reply_comments(fake_db, user_id, 15)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_supabase", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot._analyze_tone_with_claude",
        AsyncMock(return_value=FAKE_TONE_ANALYSIS),
    )

    tone = await YouTubeCommentAutopilot().learn_channel_tone("UC_test", user_id)

    assert tone.sample_size == 15
    assert tone.formality == "casual"
    assert tone.average_length == 45
    assert len(tone.representative_phrases) == 5
    assert tone.style_summary == "Warm casual Korean with gratitude expressions"

    stored = fake_db.tables["ytboost_channel_tones"]
    assert len(stored) == 1
    assert stored[0]["youtube_channel_id"] == "UC_test"


async def test_tone_learning_insufficient_samples(
    monkeypatch, fake_db, user_id
) -> None:
    """Tone learning raises error when < 10 reply samples."""
    from app.services.youtube_comment_autopilot import (
        ToneLearningError,
        YouTubeCommentAutopilot,
    )

    _make_reply_comments(fake_db, user_id, 5)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_supabase", lambda: fake_db
    )

    with pytest.raises(ToneLearningError, match="Not enough reply samples: 5 < 10"):
        await YouTubeCommentAutopilot().learn_channel_tone("UC_test", user_id)

    assert len(fake_db.tables["ytboost_channel_tones"]) == 0


async def test_tone_stored_and_retrievable(monkeypatch, fake_db, user_id) -> None:
    """Learned tone is stored and can be retrieved via get_stored_tone."""
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    _make_reply_comments(fake_db, user_id, 12)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_supabase", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot._analyze_tone_with_claude",
        AsyncMock(return_value=FAKE_TONE_ANALYSIS),
    )

    autopilot = YouTubeCommentAutopilot()
    await autopilot.learn_channel_tone("UC_test", user_id)
    stored_tone = await autopilot.get_stored_tone("UC_test", user_id)

    assert stored_tone is not None
    assert stored_tone.formality == "casual"
    assert stored_tone.average_length == 45


async def test_generate_reply_uses_tone_context(monkeypatch, fake_db, user_id) -> None:
    """generate_reply receives tone context from _build_tone_context."""
    from app.services.youtube_comment_autopilot import ChannelTone, YouTubeCommentAutopilot

    tone = ChannelTone(
        average_length=50,
        emoji_frequency=0.5,
        greeting_patterns=["감사합니다!"],
        formality="formal",
        representative_phrases=["좋은 질문이에요", "도움이 됐다니 기뻐요"],
        style_summary="Formal Korean style",
        sample_size=20,
    )

    autopilot = YouTubeCommentAutopilot()
    context = autopilot._build_tone_context(tone)

    assert "Formal Korean style" in context
    assert "formal" in context
    assert "~50 chars" in context
    assert "감사합니다!" in context
    assert "Use emojis occasionally" in context


async def test_learn_tone_endpoint_queues_task(monkeypatch, fake_db, user_id) -> None:
    """POST /channels/{id}/learn-tone returns queued status with task_id."""
    from app.api.deps import AuthenticatedUser, get_current_user
    from app.main import app

    channel_id = _make_channel(fake_db, user_id)

    test_user = AuthenticatedUser(id=user_id, email="u@test.com", plan="creator", is_test_key=True)
    app.dependency_overrides[get_current_user] = lambda: test_user
    monkeypatch.setattr("app.api.v1.ytboost.get_supabase", lambda: fake_db)

    mock_task = MagicMock()
    mock_task.id = "celery-task-123"
    monkeypatch.setattr(
        "app.api.v1.ytboost.learn_channel_tone_task",
        MagicMock(delay=MagicMock(return_value=mock_task)),
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/ytboost/channels/{channel_id}/learn-tone",
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["task_id"] == "celery-task-123"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_celery_task_learn_tone(monkeypatch, fake_db, user_id) -> None:
    """Celery task calls learn_channel_tone and returns result."""
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    _make_reply_comments(fake_db, user_id, 20)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_supabase", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot._analyze_tone_with_claude",
        AsyncMock(return_value=FAKE_TONE_ANALYSIS),
    )

    tone = await YouTubeCommentAutopilot().learn_channel_tone("UC_test", user_id)
    assert tone.sample_size == 20


async def test_learn_tone_auth_required(fake_db) -> None:
    """POST /channels/{id}/learn-tone without auth returns 401."""
    from app.api.deps import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/ytboost/channels/fake-id/learn-tone",
        )

    assert resp.status_code == 401


async def test_learn_tone_channel_not_found(monkeypatch, fake_db, user_id) -> None:
    """POST /channels/{id}/learn-tone with non-existent channel returns 404."""
    from app.api.deps import AuthenticatedUser, get_current_user
    from app.main import app

    test_user = AuthenticatedUser(id=user_id, email="u@test.com", plan="creator", is_test_key=True)
    app.dependency_overrides[get_current_user] = lambda: test_user
    monkeypatch.setattr("app.api.v1.ytboost.get_supabase", lambda: fake_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ytboost/channels/nonexistent-id/learn-tone",
            )

        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_claude_api_failure_graceful(monkeypatch, fake_db, user_id) -> None:
    """Claude API failure raises exception, doesn't store partial data."""
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    _make_reply_comments(fake_db, user_id, 15)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_supabase", lambda: fake_db
    )
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot._analyze_tone_with_claude",
        AsyncMock(side_effect=Exception("Claude API timeout")),
    )

    with pytest.raises(Exception, match="Claude API timeout"):
        await YouTubeCommentAutopilot().learn_channel_tone("UC_test", user_id)

    assert len(fake_db.tables["ytboost_channel_tones"]) == 0


async def test_tone_overwrite_on_relearn(monkeypatch, fake_db, user_id) -> None:
    """Re-learning tone overwrites the previous profile."""
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    _make_reply_comments(fake_db, user_id, 15)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_supabase", lambda: fake_db
    )

    first_analysis = {**FAKE_TONE_ANALYSIS, "formality": "formal", "average_length": 30}
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot._analyze_tone_with_claude",
        AsyncMock(return_value=first_analysis),
    )

    autopilot = YouTubeCommentAutopilot()
    tone1 = await autopilot.learn_channel_tone("UC_test", user_id)
    assert tone1.formality == "formal"
    assert tone1.average_length == 30

    second_analysis = {**FAKE_TONE_ANALYSIS, "formality": "casual", "average_length": 60}
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot._analyze_tone_with_claude",
        AsyncMock(return_value=second_analysis),
    )

    tone2 = await autopilot.learn_channel_tone("UC_test", user_id)
    assert tone2.formality == "casual"
    assert tone2.average_length == 60

    assert len(fake_db.tables["ytboost_channel_tones"]) == 1
    stored = fake_db.tables["ytboost_channel_tones"][0]
    assert stored["tone_profile"]["formality"] == "casual"
