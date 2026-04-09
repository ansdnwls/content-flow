"""Shared fixtures for adapter tests."""

from __future__ import annotations

import importlib

import pytest
import pytest_asyncio

from app.adapters.base import MediaSpec
from tests._resource_cleanup import AsyncResourceTracker, install_resource_tracking


def _reset_redis_singletons() -> None:
    module_names = (
        "app.core.webhook_dispatcher",
        "app.core.response_cache",
        "app.services.trending_service",
        "app.core.platform_limiter",
    )
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        reset = getattr(module, "reset_redis_client", None)
        if callable(reset):
            reset()
        elif hasattr(module, "_redis"):
            module._redis = None


@pytest_asyncio.fixture(autouse=True)
async def cleanup_async_resources(monkeypatch) -> None:
    tracker = AsyncResourceTracker()
    install_resource_tracking(monkeypatch, tracker)
    _reset_redis_singletons()

    yield

    try:
        from app.main import app

        app.dependency_overrides.clear()
        app_redis = getattr(getattr(app, "state", None), "redis", None)
        if app_redis is not None:
            tracker.track_redis_client(app_redis)
            app.state.redis = None
    except Exception:
        pass

    tracker.collect_garbage_resources()
    await tracker.close_all()
    _reset_redis_singletons()


@pytest.fixture
def video_media() -> list[MediaSpec]:
    return [MediaSpec(url="https://example.com/video.mp4", media_type="video")]


@pytest.fixture
def image_media() -> list[MediaSpec]:
    return [MediaSpec(url="https://example.com/image.jpg", media_type="image")]


@pytest.fixture
def multi_image_media() -> list[MediaSpec]:
    return [
        MediaSpec(url="https://example.com/img1.jpg", media_type="image"),
        MediaSpec(url="https://example.com/img2.jpg", media_type="image"),
        MediaSpec(url="https://example.com/img3.jpg", media_type="image"),
    ]
