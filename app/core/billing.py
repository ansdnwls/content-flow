"""Billing / plan-limit checks (stub — Week 2 full implementation)."""

from __future__ import annotations

from app.core.auth import AuthenticatedUser
from app.core.errors import BillingLimitError

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"posts_per_month": 20, "video_gen_per_month": 3, "social_sets": 2},
    "build": {"posts_per_month": 200, "video_gen_per_month": 20, "social_sets": 5},
    "scale": {"posts_per_month": 999_999, "video_gen_per_month": 100, "social_sets": 20},
    "enterprise": {"posts_per_month": 999_999, "video_gen_per_month": 999_999, "social_sets": 999_999},
}


async def check_post_limit(user: AuthenticatedUser) -> None:
    """Raise BillingLimitError if user exceeded monthly post quota."""
    # TODO: count posts this month from DB and compare to plan limit
    _ = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])


async def check_video_limit(user: AuthenticatedUser) -> None:
    """Raise BillingLimitError if user exceeded monthly video-gen quota."""
    _ = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
