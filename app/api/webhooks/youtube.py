"""YouTube PubSubHubbub webhook endpoints for YtBoost."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.db import get_supabase
from app.services.youtube_trigger import (
    is_known_video,
    mark_video_detected,
    parse_youtube_notification,
    verify_webhook_signature,
)
from app.workers.shorts_worker import extract_ytboost_shorts_task

router = APIRouter(prefix="/api/webhooks", tags=["YouTube Webhooks"])


@router.get(
    "/youtube/{user_id}",
    response_class=PlainTextResponse,
    summary="Verify YouTube Webhook",
    description="Responds to PubSubHubbub subscription verification challenges.",
)
async def verify_youtube_webhook(
    user_id: str,
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
) -> PlainTextResponse:
    subscription = (
        get_supabase()
        .table("ytboost_subscriptions")
        .select("id")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=f"YtBoost subscription for '{user_id}' not found",
        )
    if hub_mode and hub_mode not in {"subscribe", "unsubscribe"}:
        raise HTTPException(status_code=400, detail="Unsupported hub.mode")
    return PlainTextResponse(hub_challenge)


@router.post(
    "/youtube/{user_id}",
    status_code=202,
    summary="Receive YouTube Upload Notification",
    description="Consumes YouTube Atom feed updates and enqueues shorts extraction.",
)
async def youtube_webhook(
    user_id: str,
    request: Request,
    x_hub_signature: str | None = Header(default=None, alias="X-Hub-Signature"),
) -> dict[str, object]:
    payload = await request.body()
    if not verify_webhook_signature(payload, x_hub_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    sb = get_supabase()
    notifications = parse_youtube_notification(payload.decode("utf-8"))
    queued = 0
    duplicates = 0

    for notification in notifications:
        subscription = (
            sb.table("ytboost_subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .eq("youtube_channel_id", notification.channel_id)
            .maybe_single()
            .execute()
            .data
        )
        if not subscription:
            continue
        if is_known_video(user_id, notification.video_id):
            duplicates += 1
            continue

        await mark_video_detected(user_id, notification)
        extract_ytboost_shorts_task.delay(
            notification.video_id,
            user_id,
            notification.channel_id,
            None,
            {"title": notification.title, "published_at": notification.published_at},
        )
        sb.table("ytboost_subscriptions").update(
            {"last_checked_at": datetime.now(UTC).isoformat()}
        ).eq("id", subscription["id"]).execute()
        queued += 1

    return {
        "status": "accepted",
        "notifications": len(notifications),
        "queued": queued,
        "duplicates": duplicates,
    }
