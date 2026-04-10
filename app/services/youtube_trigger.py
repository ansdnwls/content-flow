"""YtBoost YouTube upload trigger helpers."""

from __future__ import annotations

import hashlib
import hmac
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings
from app.core.audit import record_audit
from app.core.db import get_supabase

PUBSUB_SUBSCRIBE_URL = "https://pubsubhubbub.appspot.com/subscribe"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


@dataclass(frozen=True)
class YouTubeVideoNotification:
    video_id: str
    channel_id: str
    published_at: str | None = None
    title: str | None = None


def build_callback_url(user_id: str) -> str:
    base = get_settings().ytboost_base_url.rstrip("/")
    return f"{base}/api/webhooks/youtube/{user_id}"


async def subscribe_to_channel(channel_id: str, user_id: str) -> dict[str, Any]:
    """Subscribe a user/channel pair to YouTube PubSubHubbub updates."""
    topic = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"
    payload = {
        "hub.mode": "subscribe",
        "hub.topic": topic,
        "hub.callback": build_callback_url(user_id),
        "hub.verify": "async",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(PUBSUB_SUBSCRIBE_URL, data=payload)
    return {
        "status_code": response.status_code,
        "topic": topic,
        "callback": payload["hub.callback"],
    }


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """Validate an optional HMAC signature for self-hosted forwarding flows."""
    secret = get_settings().ytboost_webhook_secret
    if not secret or not signature:
        return True

    normalized = signature
    if signature.startswith("sha1="):
        normalized = signature.split("=", 1)[1]

    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha1).hexdigest()
    return hmac.compare_digest(digest, normalized)


def parse_youtube_notification(xml_payload: str) -> list[YouTubeVideoNotification]:
    """Parse an Atom feed notification into structured entries."""
    root = ET.fromstring(xml_payload)
    notifications: list[YouTubeVideoNotification] = []

    for entry in root.findall("atom:entry", ATOM_NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=ATOM_NS)
        channel_id = entry.findtext("yt:channelId", default="", namespaces=ATOM_NS)
        if not video_id or not channel_id:
            continue
        notifications.append(
            YouTubeVideoNotification(
                video_id=video_id,
                channel_id=channel_id,
                published_at=entry.findtext("atom:published", default=None, namespaces=ATOM_NS),
                title=entry.findtext("atom:title", default=None, namespaces=ATOM_NS),
            ),
        )

    return notifications


def is_known_video(user_id: str, video_id: str) -> bool:
    """Best-effort dedup based on extracted shorts and prior audit events."""
    sb = get_supabase()
    _short_response = (
        sb.table("ytboost_shorts")
        .select("id")
        .eq("user_id", user_id)
        .eq("source_video_id", video_id)
        .limit(1)
        .execute()
    )
    _short_rows = getattr(_short_response, "data", None) or []
    existing_short = _short_rows[0] if _short_rows else None
    if existing_short:
        return True

    _audit_response = (
        sb.table("audit_logs")
        .select("id")
        .eq("user_id", user_id)
        .eq("action", "ytboost.youtube_video_detected")
        .eq("resource", f"youtube_videos/{video_id}")
        .limit(1)
        .execute()
    )
    _audit_rows = getattr(_audit_response, "data", None) or []
    existing_audit = _audit_rows[0] if _audit_rows else None
    return existing_audit is not None


async def mark_video_detected(user_id: str, video: YouTubeVideoNotification) -> None:
    await record_audit(
        user_id=user_id,
        action="ytboost.youtube_video_detected",
        resource=f"youtube_videos/{video.video_id}",
        metadata={
            "channel_id": video.channel_id,
            "published_at": video.published_at,
            "title": video.title,
            "detected_at": datetime.now(UTC).isoformat(),
        },
    )
