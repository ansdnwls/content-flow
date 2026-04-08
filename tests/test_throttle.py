"""Unit tests for compute_throttle_offsets – pure function, no I/O."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.throttle import (
    DEFAULT_THROTTLE_SECONDS,
    PLATFORM_THROTTLE_SECONDS,
    compute_throttle_offsets,
)

BASE = datetime(2026, 4, 7, 12, 0, 0, tzinfo=UTC)


def test_single_post_no_delay() -> None:
    """A single post with no prior history should return None (immediate)."""
    posts = [{"platforms": ["youtube"], "scheduled_for": None}]
    result = compute_throttle_offsets(posts, BASE)
    assert result == [None]


def test_same_platform_two_posts_staggered() -> None:
    """Two consecutive YouTube posts should be staggered by 300 s."""
    posts = [
        {"platforms": ["youtube"], "scheduled_for": None},
        {"platforms": ["youtube"], "scheduled_for": None},
    ]
    result = compute_throttle_offsets(posts, BASE)
    assert result[0] is None
    assert result[1] == BASE + timedelta(seconds=PLATFORM_THROTTLE_SECONDS["youtube"])


def test_different_platforms_no_stagger() -> None:
    """Posts targeting different platforms should all fire immediately."""
    posts = [
        {"platforms": ["youtube"], "scheduled_for": None},
        {"platforms": ["tiktok"], "scheduled_for": None},
        {"platforms": ["instagram"], "scheduled_for": None},
    ]
    result = compute_throttle_offsets(posts, BASE)
    assert result == [None, None, None]


def test_scheduled_for_preserved() -> None:
    """A post with scheduled_for keeps its time, but affects future slots."""
    scheduled = BASE + timedelta(hours=1)
    posts = [
        {"platforms": ["youtube"], "scheduled_for": scheduled},
        {"platforms": ["youtube"], "scheduled_for": None},
    ]
    result = compute_throttle_offsets(posts, BASE)
    assert result[0] == scheduled
    expected = scheduled + timedelta(seconds=PLATFORM_THROTTLE_SECONDS["youtube"])
    assert result[1] == expected


def test_cross_platform_max_gap() -> None:
    """A post targeting multiple platforms uses the max throttle gap."""
    posts = [
        {"platforms": ["youtube", "tiktok"], "scheduled_for": None},
        {"platforms": ["youtube", "tiktok"], "scheduled_for": None},
    ]
    result = compute_throttle_offsets(posts, BASE)
    assert result[0] is None
    # tiktok has the larger throttle (1800 s) so it dominates
    assert result[1] == BASE + timedelta(seconds=PLATFORM_THROTTLE_SECONDS["tiktok"])


def test_mixed_platforms_partial_stagger() -> None:
    """Mix of same-platform and cross-platform posts with default throttle."""
    posts = [
        {"platforms": ["youtube"], "scheduled_for": None},
        {"platforms": ["reddit"], "scheduled_for": None},   # different, no stagger
        {"platforms": ["youtube"], "scheduled_for": None},   # stagger from first
        {"platforms": ["reddit"], "scheduled_for": None},    # stagger from second
    ]
    result = compute_throttle_offsets(posts, BASE)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == BASE + timedelta(seconds=PLATFORM_THROTTLE_SECONDS["youtube"])
    assert result[3] == BASE + timedelta(seconds=DEFAULT_THROTTLE_SECONDS)
