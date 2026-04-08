"""Post service orchestrates multi-platform publishing with partial failure support."""

from __future__ import annotations

import json
from datetime import datetime

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult
from app.adapters.bluesky import BlueskyAdapter
from app.adapters.facebook import FacebookAdapter
from app.adapters.google_business import GoogleBusinessAdapter
from app.adapters.instagram import InstagramAdapter
from app.adapters.kakao import KakaoAdapter
from app.adapters.line import LINEAdapter
from app.adapters.linkedin import LinkedInAdapter
from app.adapters.mastodon import MastodonAdapter
from app.adapters.medium import MediumAdapter
from app.adapters.naver_blog import NaverBlogAdapter
from app.adapters.note_jp import NoteJpAdapter
from app.adapters.pinterest import PinterestAdapter
from app.adapters.reddit import RedditAdapter
from app.adapters.snapchat import SnapchatAdapter
from app.adapters.telegram import TelegramAdapter
from app.adapters.threads import ThreadsAdapter
from app.adapters.tiktok import TikTokAdapter
from app.adapters.tistory import TistoryAdapter
from app.adapters.wordpress import WordPressAdapter
from app.adapters.x_twitter import XTwitterAdapter
from app.adapters.youtube import YouTubeAdapter
from app.core.db import get_supabase
from app.core.metrics import record_platform_post
from app.core.webhook_dispatcher import dispatch_event
from app.oauth.token_store import get_valid_credentials
from app.services.notification_service import create_notification

ADAPTERS: dict[str, PlatformAdapter] = {
    "youtube": YouTubeAdapter(),
    "tiktok": TikTokAdapter(),
    "instagram": InstagramAdapter(),
    "x_twitter": XTwitterAdapter(),
    "linkedin": LinkedInAdapter(),
    "facebook": FacebookAdapter(),
    "threads": ThreadsAdapter(),
    "pinterest": PinterestAdapter(),
    "reddit": RedditAdapter(),
    "bluesky": BlueskyAdapter(),
    "snapchat": SnapchatAdapter(),
    "telegram": TelegramAdapter(),
    "wordpress": WordPressAdapter(),
    "google_business": GoogleBusinessAdapter(),
    "naver_blog": NaverBlogAdapter(),
    "tistory": TistoryAdapter(),
    "kakao": KakaoAdapter(),
    "note_jp": NoteJpAdapter(),
    "line": LINEAdapter(),
    "mastodon": MastodonAdapter(),
    "medium": MediumAdapter(),
}

def bulk_enqueue(post_ids_and_owners: list[tuple[str, str]]) -> None:
    """Dispatch multiple posts to Celery as a parallel group."""
    if not post_ids_and_owners:
        return
    from celery import group

    from app.workers.post_worker import publish_post_task

    job = group(
        publish_post_task.s(post_id, owner_id)
        for post_id, owner_id in post_ids_and_owners
    )
    job.apply_async()


async def publish_post(post_id: str, owner_id: str) -> dict[str, PublishResult]:
    """Publish a post to all target platforms and update delivery state."""
    sb = get_supabase()
    sb.table("posts").update({"status": "publishing"}).eq("id", post_id).execute()

    deliveries = (
        sb.table("post_deliveries")
        .select("id, platform, social_account_id")
        .eq("post_id", post_id)
        .execute()
        .data
    )
    post = (
        sb.table("posts")
        .select("text, media_urls, media_type, platform_options")
        .eq("id", post_id)
        .single()
        .execute()
        .data
    )

    raw_urls = post.get("media_urls") or []
    if isinstance(raw_urls, str):
        raw_urls = json.loads(raw_urls)

    media = [
        MediaSpec(url=url, media_type=post.get("media_type") or "video")
        for url in raw_urls
    ]
    results: dict[str, PublishResult] = {}
    rate_limit_blocks: list[tuple[str, str]] = []

    for delivery in deliveries:
        platform = delivery["platform"]
        adapter = ADAPTERS.get(platform)
        if not adapter or not delivery.get("social_account_id"):
            continue

        decision = await adapter.rate_limit_check(
            owner_id,
            delivery["social_account_id"],
            reserve=False,
        )
        if decision.allowed:
            continue

        next_slot = decision.next_available_at or "unknown"
        rate_limit_blocks.append((platform, next_slot))

    if rate_limit_blocks:
        next_slot = min(
            (slot for _platform, slot in rate_limit_blocks),
            key=datetime.fromisoformat,
        )
        sb.table("posts").update(
            {"status": "scheduled", "scheduled_for": next_slot},
        ).eq("id", post_id).execute()
        blocked = {platform: slot for platform, slot in rate_limit_blocks}
        for delivery in deliveries:
            platform = delivery["platform"]
            error = (
                f"Platform rate limit active. Next slot: {blocked[platform]}"
                if platform in blocked
                else f"Publish delayed until {next_slot} due to another platform limit"
            )
            sb.table("post_deliveries").update(
                {"status": "pending", "error_message": error},
            ).eq("id", delivery["id"]).execute()
            results[platform] = PublishResult(success=False, error=error)
            record_platform_post(platform, "delayed")
        return results

    for delivery in deliveries:
        platform = delivery["platform"]
        adapter = ADAPTERS.get(platform)
        if not adapter:
            result = PublishResult(success=False, error=f"No adapter for {platform}")
        elif not delivery.get("social_account_id"):
            result = PublishResult(
                success=False,
                error=f"No connected account for {platform}",
            )
        else:
            options = (post.get("platform_options") or {}).get(platform, {})
            try:
                reserved = await adapter.rate_limit_check(
                    owner_id,
                    delivery["social_account_id"],
                    reserve=True,
                )
                if not reserved.allowed:
                    result = PublishResult(
                        success=False,
                        error=(
                            "Platform rate limit active. "
                            f"Next slot: {reserved.next_available_at or 'unknown'}"
                        ),
                    )
                    sb.table("posts").update(
                        {
                            "status": "scheduled",
                            "scheduled_for": reserved.next_available_at,
                        },
                    ).eq("id", post_id).execute()
                    sb.table("post_deliveries").update(
                        {"status": "pending", "error_message": result.error},
                    ).eq("id", delivery["id"]).execute()
                    results[platform] = result
                    record_platform_post(platform, "delayed")
                    continue
                credentials = await get_valid_credentials(
                    delivery["social_account_id"],
                    owner_id,
                )
                result = await adapter.publish(post.get("text"), media, options, credentials)
            except Exception as exc:  # pragma: no cover - defensive for external adapters
                result = PublishResult(success=False, error=str(exc))

        sb.table("post_deliveries").update(
            {
                "status": "published" if result.success else "failed",
                "platform_post_id": result.platform_post_id,
                "error_message": result.error,
            },
        ).eq("id", delivery["id"]).execute()
        results[platform] = result
        record_platform_post(platform, "published" if result.success else "failed")

    successes = sum(1 for result in results.values() if result.success)
    if successes == len(results):
        overall = "published"
    elif successes > 0:
        overall = "partially_failed"
    else:
        overall = "failed"

    sb.table("posts").update({"status": overall}).eq("id", post_id).execute()
    if overall == "published":
        await dispatch_event(
            owner_id,
            "post.published",
            {"post_id": post_id, "platforms": list(results.keys())},
        )
        try:
            platforms_str = ", ".join(results.keys())
            create_notification(
                user_id=owner_id,
                type="post_published",
                title="Post published",
                body=f"Your post was published to {platforms_str}.",
                link_url=f"/posts/{post_id}",
            )
        except Exception:
            pass

    return results
