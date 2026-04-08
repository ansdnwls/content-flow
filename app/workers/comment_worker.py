"""Worker tasks for periodic comment collection and auto-reply."""

from __future__ import annotations

import asyncio

from app.core.db import get_supabase
from app.services.comment_service import CommentService
from app.workers.celery_app import celery_app


async def run_collect_all_comments() -> dict:
    """Collect comments for all active post deliveries."""
    sb = get_supabase()
    deliveries = (
        sb.table("post_deliveries")
        .select("platform, platform_post_id, owner_id")
        .eq("status", "published")
        .execute()
        .data
    )

    accounts_result = sb.table("social_accounts").select("*").execute()
    accounts_by_owner: dict[str, dict[str, dict]] = {}
    for acct in accounts_result.data:
        owner = acct["owner_id"]
        platform = acct["platform"]
        accounts_by_owner.setdefault(owner, {})[platform] = {
            "access_token": acct.get("encrypted_access_token", ""),
            "ig_user_id": acct.get("metadata", {}).get("ig_user_id", ""),
        }

    service = CommentService()
    collected_total = 0

    for delivery in deliveries:
        owner_id = delivery["owner_id"]
        platform = delivery["platform"]
        creds = accounts_by_owner.get(owner_id, {}).get(platform)
        if not creds:
            continue

        stored = await service.collect_comments(
            user_id=owner_id,
            platform=platform,
            platform_post_id=delivery["platform_post_id"],
            credentials=creds,
        )
        collected_total += len(stored)

    return {"collected": collected_total, "deliveries_scanned": len(deliveries)}


async def run_auto_reply_pending() -> dict:
    """Auto-reply to all pending comments."""
    sb = get_supabase()
    pending = (
        sb.table("comments")
        .select("id, user_id, platform")
        .eq("reply_status", "pending")
        .execute()
        .data
    )

    accounts_result = sb.table("social_accounts").select("*").execute()
    accounts_by_owner: dict[str, dict[str, dict]] = {}
    for acct in accounts_result.data:
        owner = acct["owner_id"]
        platform = acct["platform"]
        accounts_by_owner.setdefault(owner, {})[platform] = {
            "access_token": acct.get("encrypted_access_token", ""),
        }

    service = CommentService()
    replied = 0
    failed = 0

    for comment in pending:
        creds = accounts_by_owner.get(
            comment["user_id"], {},
        ).get(comment["platform"])
        if not creds:
            continue

        result = await service.auto_reply(
            comment_id=comment["id"],
            user_id=comment["user_id"],
            credentials=creds,
        )
        if result.get("success"):
            replied += 1
        else:
            failed += 1

    return {"replied": replied, "failed": failed, "total_pending": len(pending)}


@celery_app.task(name="contentflow.collect_comments")
def collect_comments_task() -> dict:
    return asyncio.run(run_collect_all_comments())


@celery_app.task(name="contentflow.auto_reply_comments")
def auto_reply_comments_task() -> dict:
    return asyncio.run(run_auto_reply_pending())


@celery_app.task(name="contentflow.learn_channel_tone")
def learn_channel_tone_task(channel_id: str, user_id: str) -> dict:
    """Celery task: learn tone for a YouTube channel."""
    from app.services.youtube_comment_autopilot import (
        ToneLearningError,
        YouTubeCommentAutopilot,
    )

    try:
        tone = asyncio.run(
            YouTubeCommentAutopilot().learn_channel_tone(channel_id, user_id)
        )
        return {"status": "completed", "sample_size": tone.sample_size}
    except ToneLearningError as exc:
        return {"status": "failed", "error": exc.reason}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
