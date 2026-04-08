"""Operational health and metrics endpoints."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from redis.asyncio import Redis

from app.config import get_settings
from app.core.db import get_supabase
from app.core.metrics import render_prometheus_text, set_runtime_gauges
from app.workers.celery_app import celery_app

router = APIRouter(tags=["ops"])


async def check_supabase_ready() -> bool:
    get_supabase().table("users").select("id").range(0, 0).execute()
    return True


async def check_redis_ready() -> bool:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        return bool(await redis.ping())
    finally:
        await redis.aclose()


def check_celery_ready() -> bool:
    inspector = celery_app.control.inspect(timeout=1.0)
    workers = inspector.ping() or {}
    return bool(workers)


async def _queue_depth() -> int:
    broker = get_settings().effective_celery_broker_url
    parsed = urlparse(broker)
    queue_name = "contentflow.default"
    redis = Redis.from_url(broker, decode_responses=True)
    try:
        if parsed.scheme.startswith("redis"):
            return int(await redis.llen(queue_name))
        return 0
    finally:
        await redis.aclose()


def _active_workers() -> int:
    inspector = celery_app.control.inspect(timeout=1.0)
    workers = inspector.ping() or {}
    return len(workers)


async def collect_runtime_metrics() -> dict[str, int]:
    db_connections = 1 if await check_supabase_ready() else 0
    active_workers = _active_workers()
    queue_depth = await _queue_depth()
    snapshot = {
        "active_workers": active_workers,
        "queue_depth": queue_depth,
        "db_connections": db_connections,
    }
    set_runtime_gauges(**snapshot)
    return snapshot


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": get_settings().app_env}


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "environment": get_settings().app_env}


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict:
    checks = {
        "supabase": await check_supabase_ready(),
        "redis": await check_redis_ready(),
        "celery": check_celery_ready(),
    }
    status = "ready" if all(checks.values()) else "degraded"
    payload = {"status": status, "checks": checks}
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=payload)
    return payload


@router.get("/health/metrics")
async def health_metrics() -> dict:
    return await collect_runtime_metrics()


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    if not get_settings().prometheus_enabled:
        raise HTTPException(status_code=404, detail="Prometheus metrics disabled")
    await collect_runtime_metrics()
    return PlainTextResponse(
        render_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
