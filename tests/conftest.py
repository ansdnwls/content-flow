"""Shared fixtures for adapter tests."""

from __future__ import annotations

import pytest

from app.adapters.base import MediaSpec


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
