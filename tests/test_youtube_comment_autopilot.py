from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.adapters.base import ReplyResult
from tests.fakes import FakeSupabase


async def test_learn_channel_tone_persists_profile(monkeypatch) -> None:
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    fake = FakeSupabase()
    user_id = str(uuid4())
    fake.insert_row(
        "comments",
        {
            "user_id": user_id,
            "platform": "youtube",
            "platform_post_id": "vid_1",
            "platform_comment_id": "c1",
            "author_id": "a1",
            "author_name": "Alice",
            "text": "Nice",
            "ai_reply": "Thanks for watching?",
            "reply_status": "replied",
        },
    )
    fake.insert_row(
        "comments",
        {
            "user_id": user_id,
            "platform": "youtube",
            "platform_post_id": "vid_2",
            "platform_comment_id": "c2",
            "author_id": "a2",
            "author_name": "Bob",
            "text": "Cool",
            "ai_reply": "Appreciate it.",
            "reply_status": "replied",
        },
    )

    monkeypatch.setattr("app.services.youtube_comment_autopilot.get_supabase", lambda: fake)

    tone = await YouTubeCommentAutopilot().learn_channel_tone("chan_123", user_id)

    assert tone.sample_size == 2
    assert fake.tables["ytboost_channel_tones"][0]["youtube_channel_id"] == "chan_123"


async def test_run_for_channel_review_mode_prepares_replies(monkeypatch) -> None:
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    fake = FakeSupabase()
    user_id = str(uuid4())
    fake.insert_row(
        "social_accounts",
        {
            "owner_id": user_id,
            "platform": "youtube",
            "handle": "channel",
            "encrypted_access_token": "tok",
            "metadata": {},
        },
    )

    class FakeCommentService:
        async def collect_comments(self, **kwargs):
            row = fake.insert_row(
                "comments",
                {
                    "user_id": user_id,
                    "platform": "youtube",
                    "platform_post_id": kwargs["platform_post_id"],
                    "platform_comment_id": f"pc_{uuid4().hex[:8]}",
                    "author_id": "a1",
                    "author_name": "Alice",
                    "text": "How do I start?",
                    "comment_created_at": datetime.now(UTC).isoformat(),
                    "reply_status": "pending",
                    "ai_reply": None,
                    "platform_reply_id": None,
                },
            )
            return [row]

        async def generate_reply(self, comment_text, context=""):
            return "Start with one upload per week."

    async def fake_credentials(*args, **kwargs):
        return {"access_token": "tok"}

    monkeypatch.setattr("app.services.youtube_comment_autopilot.get_supabase", lambda: fake)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_valid_credentials",
        fake_credentials,
    )

    autopilot = YouTubeCommentAutopilot()
    autopilot.comment_service = FakeCommentService()

    result = await autopilot.run_for_channel(
        "chan_123",
        user_id,
        mode="review",
        recent_video_ids=["vid_1"],
    )

    assert result == {"collected": 1, "prepared": 1, "replied": 0}
    assert fake.tables["comments"][0]["reply_status"] == "review_pending"
    assert fake.tables["comments"][0]["ai_reply"] == "Start with one upload per week."


async def test_approve_reply_posts_and_updates_comment(monkeypatch) -> None:
    from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot

    fake = FakeSupabase()
    user_id = str(uuid4())
    comment_id = str(uuid4())
    fake.insert_row(
        "social_accounts",
        {
            "owner_id": user_id,
            "platform": "youtube",
            "handle": "channel",
            "encrypted_access_token": "tok",
            "metadata": {},
        },
    )
    fake.insert_row(
        "comments",
        {
            "id": comment_id,
            "user_id": user_id,
            "platform": "youtube",
            "platform_post_id": "vid_1",
            "platform_comment_id": "comment_1",
            "author_id": "a1",
            "author_name": "Alice",
            "text": "Nice video",
            "ai_reply": "Thanks for watching!",
            "reply_status": "review_pending",
        },
    )

    class FakeAdapter:
        async def reply_comment(self, *args, **kwargs):
            return ReplyResult(success=True, platform_comment_id="reply_1")

    async def fake_credentials(*args, **kwargs):
        return {"access_token": "tok"}

    monkeypatch.setattr("app.services.youtube_comment_autopilot.get_supabase", lambda: fake)
    monkeypatch.setattr(
        "app.services.youtube_comment_autopilot.get_valid_credentials",
        fake_credentials,
    )
    monkeypatch.setattr("app.services.youtube_comment_autopilot.YouTubeAdapter", FakeAdapter)

    result = await YouTubeCommentAutopilot().approve_reply(comment_id, user_id)

    assert result["success"] is True
    assert result["platform_reply_id"] == "reply_1"
    assert fake.tables["comments"][0]["reply_status"] == "replied"
