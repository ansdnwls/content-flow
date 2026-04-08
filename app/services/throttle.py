"""Platform-aware throttle offsets for bulk post scheduling."""

from __future__ import annotations

from datetime import datetime, timedelta

PLATFORM_THROTTLE_SECONDS: dict[str, int] = {
    "youtube": 300,
    "tiktok": 1800,
    "instagram": 900,
}
DEFAULT_THROTTLE_SECONDS = 60


def compute_throttle_offsets(
    posts: list[dict],
    base_time: datetime,
) -> list[datetime | None]:
    """Compute per-post scheduled times respecting platform throttle gaps.

    Each entry in *posts* must contain:
      - ``platforms``: list[str]
      - ``scheduled_for``: datetime | str | None

    Returns a list parallel to *posts* where each element is:
      - ``None``  – post can fire immediately (no throttle needed)
      - ``datetime`` – the earliest time the post should be dispatched

    Rules:
      1. Consecutive posts targeting the **same platform** are staggered by
         that platform's throttle interval.
      2. Posts that already carry ``scheduled_for`` keep their time but update
         the per-platform "last slot" tracker.
      3. Cross-platform posts (multiple platforms) use the **max** gap across
         all targeted platforms.
    """
    last_slot: dict[str, datetime] = {}
    results: list[datetime | None] = []

    for post in posts:
        platforms: list[str] = post.get("platforms", [])
        scheduled_for = post.get("scheduled_for")

        if scheduled_for is not None:
            if isinstance(scheduled_for, str):
                scheduled_for = datetime.fromisoformat(scheduled_for)
            results.append(scheduled_for)
            for platform in platforms:
                prev = last_slot.get(platform, base_time)
                last_slot[platform] = max(prev, scheduled_for)
            continue

        # Compute the earliest slot that satisfies every target platform.
        earliest = base_time
        needs_delay = False
        for platform in platforms:
            if platform not in last_slot:
                continue
            throttle = timedelta(
                seconds=PLATFORM_THROTTLE_SECONDS.get(
                    platform, DEFAULT_THROTTLE_SECONDS
                ),
            )
            candidate = last_slot[platform] + throttle
            if candidate > earliest:
                earliest = candidate
                needs_delay = True

        if needs_delay:
            results.append(earliest)
        else:
            results.append(None)

        slot_time = earliest
        for platform in platforms:
            last_slot[platform] = slot_time

    return results
