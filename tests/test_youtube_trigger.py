from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace
from uuid import uuid4

import httpx
import respx
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeSupabase

YOUTUBE_XML = """
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <entry>
    <yt:videoId>vid_123</yt:videoId>
    <yt:channelId>chan_123</yt:channelId>
    <title>Fresh upload</title>
    <published>2026-04-08T00:00:00+00:00</published>
  </entry>
</feed>
""".strip()


@respx.mock
async def test_subscribe_to_channel_posts_pubsub_request(monkeypatch) -> None:
    from app.services.youtube_trigger import PUBSUB_SUBSCRIBE_URL, subscribe_to_channel

    monkeypatch.setattr(
        "app.services.youtube_trigger.get_settings",
        lambda: SimpleNamespace(
            ytboost_base_url="https://api.example.com",
            ytboost_webhook_secret=None,
        ),
    )
    route = respx.post(PUBSUB_SUBSCRIBE_URL).mock(return_value=httpx.Response(202))

    result = await subscribe_to_channel("chan_123", "user_123")

    assert route.called is True
    assert result["status_code"] == 202
    assert result["callback"] == "https://api.example.com/api/webhooks/youtube/user_123"


def test_parse_notification_and_verify_signature(monkeypatch) -> None:
    from app.services.youtube_trigger import parse_youtube_notification, verify_webhook_signature

    secret = "top-secret"
    monkeypatch.setattr(
        "app.services.youtube_trigger.get_settings",
        lambda: SimpleNamespace(ytboost_webhook_secret=secret),
    )

    payload = YOUTUBE_XML.encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha1).hexdigest()

    notifications = parse_youtube_notification(YOUTUBE_XML)
    assert len(notifications) == 1
    assert notifications[0].video_id == "vid_123"
    assert notifications[0].channel_id == "chan_123"
    assert verify_webhook_signature(payload, f"sha1={signature}") is True


async def test_yt_factory_integration_queues_only_new_video(monkeypatch) -> None:
    from app.services.yt_factory_integration import YtFactoryIntegration

    queued: list[tuple] = []
    marked: list[str] = []

    class FakeTask:
        @staticmethod
        def delay(*args):
            queued.append(args)

    async def fake_mark(user_id, video):
        marked.append(f"{user_id}:{video.video_id}")

    monkeypatch.setattr("app.services.yt_factory_integration.is_known_video", lambda *_: False)
    monkeypatch.setattr("app.services.yt_factory_integration.mark_video_detected", fake_mark)
    monkeypatch.setattr(
        "app.services.yt_factory_integration.extract_ytboost_shorts_task",
        FakeTask(),
    )

    result = await YtFactoryIntegration().handle_publish_complete(
        user_id="user_123",
        youtube_video_id="vid_123",
        youtube_channel_id="chan_123",
        transcript=[{"start": 0, "text": "hook"}],
        video_metadata={"title": "Fresh upload"},
    )

    assert result["queued"] is True
    assert marked == ["user_123:vid_123"]
    assert queued[0][:3] == ("vid_123", "user_123", "chan_123")


async def test_youtube_webhook_verification_and_enqueue(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    user_id = str(uuid4())
    fake.insert_row(
        "ytboost_subscriptions",
        {
            "user_id": user_id,
            "youtube_channel_id": "chan_123",
            "channel_name": "Founder",
        },
    )

    queued: list[tuple] = []

    class FakeTask:
        @staticmethod
        def delay(*args):
            queued.append(args)

    async def fake_mark(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.webhooks.youtube.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.webhooks.youtube.is_known_video", lambda *_: False)
    monkeypatch.setattr("app.api.webhooks.youtube.mark_video_detected", fake_mark)
    monkeypatch.setattr("app.api.webhooks.youtube.extract_ytboost_shorts_task", FakeTask())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        verify = await client.get(
            f"/api/webhooks/youtube/{user_id}",
            params={"hub.challenge": "abc123", "hub.mode": "subscribe"},
        )
        assert verify.status_code == 200
        assert verify.text == "abc123"

        notify = await client.post(
            f"/api/webhooks/youtube/{user_id}",
            content=YOUTUBE_XML.encode("utf-8"),
            headers={"content-type": "application/atom+xml"},
        )

    assert notify.status_code == 202
    assert notify.json()["queued"] == 1
    assert queued[0][:3] == ("vid_123", user_id, "chan_123")
