"""Worker tasks for content bomb transformation and publication."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.core.db import get_supabase
from app.core.webhook_dispatcher import dispatch_event
from app.services.content_transformer import ContentTransformer
from app.workers.celery_app import celery_app


async def run_bomb_transform(bomb_id: str, user_id: str) -> dict:
    sb = get_supabase()
    sb.table("bombs").update({"status": "transforming"}).eq("id", bomb_id).execute()
    bomb = (
        sb.table("bombs")
        .select("id, topic")
        .eq("id", bomb_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    transformer = ContentTransformer()
    platform_contents = await transformer.transform_topic(bomb["topic"])
    sb.table("bombs").update(
        {"status": "ready", "platform_contents": platform_contents},
    ).eq("id", bomb_id).execute()
    return (
        sb.table("bombs").select("*").eq("id", bomb_id).maybe_single().execute().data
    )


async def run_bomb_publish(bomb_id: str, user_id: str) -> dict:
    sb = get_supabase()
    bomb = (
        sb.table("bombs")
        .select("*")
        .eq("id", bomb_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    contents = bomb.get("platform_contents") or {}
    updated_contents = {}
    for platform, content in contents.items():
        updated_contents[platform] = {
            **content,
            "publish_status": "published",
            "published_at": datetime.now(UTC).isoformat(),
        }
    sb.table("bombs").update(
        {"status": "published", "platform_contents": updated_contents},
    ).eq("id", bomb_id).execute()
    await dispatch_event(
        user_id,
        "post.published",
        {"bomb_id": bomb_id, "platforms": list(updated_contents)},
    )
    return (
        sb.table("bombs").select("*").eq("id", bomb_id).maybe_single().execute().data
    )


@celery_app.task(name="contentflow.transform_bomb")
def transform_bomb_task(bomb_id: str, user_id: str) -> dict:
    return asyncio.run(run_bomb_transform(bomb_id, user_id))


@celery_app.task(name="contentflow.publish_bomb")
def publish_bomb_task(bomb_id: str, user_id: str) -> dict:
    return asyncio.run(run_bomb_publish(bomb_id, user_id))
