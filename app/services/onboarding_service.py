"""Onboarding service — step-by-step guide with progress tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.db import get_supabase
from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class StepDef:
    """Definition of a single onboarding step."""

    id: str
    title: str
    description: str
    optional: bool = False


STEPS: tuple[StepDef, ...] = (
    StepDef(
        id="welcome",
        title="Welcome to ContentFlow",
        description="Your account has been created.",
    ),
    StepDef(
        id="verify_email",
        title="Verify your email",
        description="Confirm your email address to unlock all features.",
    ),
    StepDef(
        id="connect_first_account",
        title="Connect a social account",
        description="Link at least one platform via OAuth (YouTube, TikTok, etc.).",
    ),
    StepDef(
        id="create_first_post",
        title="Create your first post",
        description="Publish or schedule a post (dry_run counts too).",
    ),
    StepDef(
        id="explore_dashboard",
        title="Explore the dashboard",
        description="Visit key pages: analytics, schedules, and settings.",
    ),
    StepDef(
        id="setup_webhook",
        title="Set up a webhook",
        description="Configure a webhook endpoint for real-time events.",
        optional=True,
    ),
)

STEP_IDS = frozenset(s.id for s in STEPS)
STEP_ORDER = {s.id: i for i, s in enumerate(STEPS)}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def init_progress(user_id: str) -> list[dict[str, Any]]:
    """Create the welcome step as auto-completed for a new user.

    Called right after signup. Returns the inserted row(s).
    """
    sb = get_supabase()

    existing = (
        sb.table("onboarding_progress")
        .select("id")
        .eq("user_id", user_id)
        .eq("step", "welcome")
        .execute()
        .data
    )
    if existing:
        return existing

    row = {
        "user_id": user_id,
        "step": "welcome",
        "completed_at": _now_iso(),
        "data": {"auto": True},
    }
    return sb.table("onboarding_progress").insert(row).execute().data


def get_progress(user_id: str) -> dict[str, Any]:
    """Return current onboarding state for the user.

    Returns:
        {
            "steps": [{"id", "title", "description", "optional",
                       "completed", "completed_at", "data"}],
            "completed_count": int,
            "total_steps": int,
            "progress_pct": int,
            "all_complete": bool,
        }
    """
    sb = get_supabase()
    rows = (
        sb.table("onboarding_progress")
        .select("*")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    completed_map: dict[str, dict[str, Any]] = {
        r["step"]: r for r in rows if r.get("completed_at")
    }

    steps_out: list[dict[str, Any]] = []
    for step_def in STEPS:
        done_row = completed_map.get(step_def.id)
        steps_out.append({
            "id": step_def.id,
            "title": step_def.title,
            "description": step_def.description,
            "optional": step_def.optional,
            "completed": done_row is not None,
            "completed_at": done_row["completed_at"] if done_row else None,
            "data": done_row.get("data") if done_row else None,
        })

    completed_count = sum(1 for s in steps_out if s["completed"])
    total = len(STEPS)
    return {
        "steps": steps_out,
        "completed_count": completed_count,
        "total_steps": total,
        "progress_pct": int(completed_count / total * 100) if total else 0,
        "all_complete": completed_count == total,
    }


def complete_step(
    user_id: str, step: str, data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark a step as completed. Returns updated progress.

    Raises ValueError if step is not valid.
    """
    if step not in STEP_IDS:
        msg = f"Unknown onboarding step: {step}"
        raise ValueError(msg)

    sb = get_supabase()

    existing = (
        sb.table("onboarding_progress")
        .select("id, completed_at")
        .eq("user_id", user_id)
        .eq("step", step)
        .execute()
        .data
    )

    if existing and existing[0].get("completed_at"):
        return get_progress(user_id)

    now = _now_iso()
    if existing:
        sb.table("onboarding_progress").update(
            {"completed_at": now, "data": data or {}},
        ).eq("id", existing[0]["id"]).execute()
    else:
        sb.table("onboarding_progress").insert({
            "user_id": user_id,
            "step": step,
            "completed_at": now,
            "data": data or {},
        }).execute()

    progress = get_progress(user_id)
    if progress["all_complete"]:
        _on_all_complete(user_id)
    return progress


def skip_remaining(user_id: str) -> dict[str, Any]:
    """Mark all incomplete steps as completed (skipped). Returns updated progress."""
    sb = get_supabase()
    rows = (
        sb.table("onboarding_progress")
        .select("step")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    done_steps = {r["step"] for r in rows if r.get("step")}

    now = _now_iso()
    for step_def in STEPS:
        if step_def.id not in done_steps:
            sb.table("onboarding_progress").insert({
                "user_id": user_id,
                "step": step_def.id,
                "completed_at": now,
                "data": {"skipped": True},
            }).execute()

    progress = get_progress(user_id)
    if progress["all_complete"]:
        _on_all_complete(user_id)
    return progress


def get_next_action(user_id: str) -> dict[str, Any] | None:
    """Return the next incomplete step with guidance, or None if all done."""
    progress = get_progress(user_id)

    for step in progress["steps"]:
        if not step["completed"]:
            hints = _step_hints(step["id"])
            return {
                "step": step["id"],
                "title": step["title"],
                "description": step["description"],
                "optional": step["optional"],
                "hints": hints,
            }

    return None


def _step_hints(step_id: str) -> dict[str, Any]:
    """Return contextual hints/links for each step."""
    hints: dict[str, dict[str, Any]] = {
        "verify_email": {
            "action": "Check your inbox and click the verification link.",
            "endpoint": "POST /api/v1/email-verify/send",
        },
        "connect_first_account": {
            "action": "Connect a social account via OAuth.",
            "endpoint": "GET /api/v1/accounts/connect/{platform}",
            "platforms": ["youtube", "tiktok", "instagram", "x"],
        },
        "create_first_post": {
            "action": "Create and publish (or dry-run) your first post.",
            "endpoint": "POST /api/v1/posts",
        },
        "explore_dashboard": {
            "action": "Visit analytics, schedules, and settings pages.",
            "pages": ["/analytics", "/schedules", "/settings"],
        },
        "setup_webhook": {
            "action": "Register a webhook URL for real-time event notifications.",
            "endpoint": "POST /api/v1/webhooks",
        },
    }
    return hints.get(step_id, {})


def _on_all_complete(user_id: str) -> None:
    """Fire side effects when user completes all onboarding steps."""
    from app.services.notification_service import create_notification

    try:
        create_notification(
            user_id=user_id,
            type="onboarding_complete",
            title="Onboarding complete!",
            body="You've finished all setup steps. You're ready to publish!",
            link_url="/dashboard",
        )
    except Exception:
        logger.exception("Failed to create onboarding completion notification")

    sb = get_supabase()
    sb.table("users").update(
        {"onboarding_completed": True},
    ).eq("id", user_id).execute()

    logger.info("Onboarding complete", user_id=user_id)
