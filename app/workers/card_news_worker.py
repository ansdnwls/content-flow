"""Celery worker for card news generation."""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging_config import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _run_card_news(
    source_type: str,
    source: str,
    *,
    title: str | None = None,
    channel_name: str | None = None,
) -> dict[str, Any]:
    """Async card news generation pipeline."""
    from app.services.content_fetcher import ContentFetcher
    from app.services.card_news_generator import CardNewsGenerator

    # 1. Fetch content
    fetcher = ContentFetcher()
    kwargs: dict[str, Any] = {}
    if source_type == "text" and title:
        kwargs["title"] = title
    content = await fetcher.fetch(source_type, source, **kwargs)

    # 2. Generate cards
    gen = CardNewsGenerator()
    result = await gen.generate_from_text(
        title=content.title,
        text=content.text,
        source_id=content.source_id,
    )

    return {
        "success": result.success,
        "source_type": source_type,
        "source_id": content.source_id,
        "card_count": result.card_count,
        "output_dir": result.output_dir,
        "color_theme": result.color_theme,
        "image_paths": result.image_paths,
        "error": result.error,
    }


@celery_app.task(name="contentflow.generate_card_news")
def generate_card_news_task(
    source_type: str,
    source: str,
    title: str | None = None,
    channel_name: str | None = None,
) -> dict[str, Any]:
    """Celery task wrapper for card news generation."""
    logger.info(
        "card_news_task_start",
        source_type=source_type,
        source=source[:50],
    )
    result = asyncio.run(
        _run_card_news(
            source_type,
            source,
            title=title,
            channel_name=channel_name,
        )
    )
    logger.info(
        "card_news_task_done",
        source_type=source_type,
        success=result["success"],
        cards=result["card_count"],
    )
    return result
