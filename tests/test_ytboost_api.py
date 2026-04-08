from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.services.ytboost_distributor import DistributionResult
from tests.fakes import FakeSupabase


def _setup_user_and_key(fake: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row(
        "users",
        {"id": user_id, "email": "ytboost@example.com", "plan": "free"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


async def _noop_invalidate(*args, **kwargs) -> int:
    return 0


async def test_ytboost_channels_crud(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake)

    async def fake_subscribe(channel_id: str, user_id: str):
        return {"status_code": 202, "channel_id": channel_id, "user_id": user_id}

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.ytboost.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.ytboost.subscribe_to_channel", fake_subscribe)
    monkeypatch.setattr("app.api.v1.ytboost.invalidate_user_cache", _noop_invalidate)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        created = await client.post(
            "/api/v1/ytboost/channels",
            json={
                "youtube_channel_id": "chan_123",
                "channel_name": "Founder",
                "auto_distribute": True,
                "target_platforms": ["youtube_shorts", "tiktok"],
                "auto_comment_mode": "review",
            },
        )
        listed = await client.get("/api/v1/ytboost/channels")
        channel_id = created.json()["id"]
        updated = await client.patch(
            f"/api/v1/ytboost/channels/{channel_id}",
            json={"auto_comment_mode": "auto"},
        )
        deleted = await client.delete(f"/api/v1/ytboost/channels/{channel_id}")

    assert created.status_code == 201
    assert listed.json()[0]["youtube_channel_id"] == "chan_123"
    assert updated.json()["auto_comment_mode"] == "auto"
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


async def test_ytboost_shorts_extract_approve_reject(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake)
    fake.insert_row(
        "ytboost_subscriptions",
        {
            "user_id": user_id,
            "youtube_channel_id": "chan_123",
            "target_platforms": ["youtube_shorts", "instagram_reels"],
        },
    )

    async def fake_extract(video_id, user_id, source_channel_id, **kwargs):
        return [
            fake.insert_row(
                "ytboost_shorts",
                {
                    "user_id": user_id,
                    "source_video_id": video_id,
                    "source_channel_id": source_channel_id,
                    "start_seconds": 0,
                    "end_seconds": 55,
                    "hook_line": "Hook",
                    "suggested_title": "Best moment",
                    "suggested_hashtags": ["#shorts"],
                    "reason": "Strong opening",
                    "clip_file_url": "https://cdn.example.com/clip.mp4",
                    "status": "pending",
                },
            )
        ]

    async def fake_distribute(self, short_clip, target_platforms, user_id):
        return [
            DistributionResult(
                requested_platform=target_platforms[0],
                adapter_platform="youtube",
                status="queued",
                post_id="post_123",
            )
        ]

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.ytboost.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.ytboost.extract_shorts", fake_extract)
    monkeypatch.setattr(
        "app.api.v1.ytboost.YtBoostDistributor.distribute_short",
        fake_distribute,
    )
    monkeypatch.setattr("app.api.v1.ytboost.invalidate_user_cache", _noop_invalidate)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        extracted = await client.post(
            "/api/v1/ytboost/shorts/extract",
            json={"video_id": "vid_123", "source_channel_id": "chan_123"},
        )
        short_id = extracted.json()["data"][0]["id"]
        approved = await client.post(f"/api/v1/ytboost/shorts/{short_id}/approve", json={})
        second_short = fake.insert_row(
            "ytboost_shorts",
            {
                "user_id": user_id,
                "source_video_id": "vid_999",
                "source_channel_id": "chan_123",
                "start_seconds": 15,
                "end_seconds": 70,
                "status": "pending",
            },
        )
        rejected = await client.post(f"/api/v1/ytboost/shorts/{second_short['id']}/reject")

    assert extracted.status_code == 201
    assert approved.json()["short"]["status"] == "distributed"
    assert approved.json()["distributions"][0]["post_id"] == "post_123"
    assert rejected.json()["status"] == "rejected"


async def test_ytboost_pending_comments_and_approval(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake)
    comment_id = str(uuid4())
    fake.insert_row(
        "comments",
        {
            "id": comment_id,
            "user_id": user_id,
            "platform": "youtube",
            "platform_post_id": "vid_123",
            "platform_comment_id": "comment_1",
            "author_id": "a1",
            "author_name": "Alice",
            "text": "Need help",
            "ai_reply": "Draft reply",
            "reply_status": "review_pending",
        },
    )

    async def fake_approve_reply(self, comment_id: str, user_id: str, **kwargs):
        return {
            "success": True,
            "platform_reply_id": "reply_1",
            "error": None,
            "ai_reply": kwargs.get("text") or "Draft reply",
        }

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.ytboost.get_supabase", lambda: fake)
    monkeypatch.setattr(
        "app.api.v1.ytboost.YouTubeCommentAutopilot.approve_reply",
        fake_approve_reply,
    )
    monkeypatch.setattr("app.api.v1.ytboost.invalidate_user_cache", _noop_invalidate)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        pending = await client.get("/api/v1/ytboost/comments/pending")
        approved = await client.post(f"/api/v1/ytboost/comments/{comment_id}/approve", json={})
        edited = await client.post(
            f"/api/v1/ytboost/comments/{comment_id}/edit",
            json={"text": "Edited reply"},
        )

    assert pending.status_code == 200
    assert pending.json()["total"] == 1
    assert approved.json()["platform_reply_id"] == "reply_1"
    assert edited.json()["ai_reply"] == "Edited reply"
