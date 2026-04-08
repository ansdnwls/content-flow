"""Onboarding API — guides new users through setup steps."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.db import get_supabase

router = APIRouter(
    prefix="/onboarding", tags=["Onboarding"], responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

ONBOARDING_STEPS = [
    "verify_email",
    "create_api_key",
    "connect_first_account",
    "first_post",
    "first_video",
]


class StepStatus(BaseModel):
    id: str
    completed: bool


class OnboardingStatusResponse(BaseModel):
    steps: list[StepStatus]
    progress: int


class OnboardingCompleteResponse(BaseModel):
    completed: bool


def _compute_steps(user: dict) -> list[StepStatus]:
    """Derive step completion from user data and related tables."""
    saved = user.get("onboarding_steps") or {}
    sb = get_supabase()
    user_id = user["id"]

    checks: dict[str, bool] = {
        "verify_email": bool(user.get("email_verified")),
        "create_api_key": (
            len(
                sb.table("api_keys")
                .select("id")
                .eq("user_id", user_id)
                .execute()
                .data,
            )
            > 1  # auth key + at least one more
        ),
        "connect_first_account": (
            len(
                sb.table("social_accounts")
                .select("id")
                .eq("owner_id", user_id)
                .execute()
                .data,
            )
            > 0
        ),
        "first_post": (
            len(
                sb.table("posts")
                .select("id")
                .eq("owner_id", user_id)
                .execute()
                .data,
            )
            > 0
        ),
        "first_video": (
            len(
                sb.table("video_jobs")
                .select("id")
                .eq("owner_id", user_id)
                .execute()
                .data,
            )
            > 0
        ),
    }

    for step_id in ONBOARDING_STEPS:
        if saved.get(step_id) == "skipped":
            checks[step_id] = True

    return [StepStatus(id=s, completed=checks.get(s, False)) for s in ONBOARDING_STEPS]


@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
    summary="Get Onboarding Status",
)
async def get_onboarding_status(user: CurrentUser) -> OnboardingStatusResponse:
    sb = get_supabase()
    row = (
        sb.table("users")
        .select("*")
        .eq("id", user.id)
        .single()
        .execute()
        .data
    )
    steps = _compute_steps(row)
    done = sum(1 for s in steps if s.completed)
    progress = int(done / len(steps) * 100) if steps else 0
    return OnboardingStatusResponse(steps=steps, progress=progress)


@router.post(
    "/skip/{step}",
    response_model=OnboardingStatusResponse,
    summary="Skip Onboarding Step",
)
async def skip_step(step: str, user: CurrentUser) -> OnboardingStatusResponse:
    sb = get_supabase()
    row = (
        sb.table("users")
        .select("*")
        .eq("id", user.id)
        .single()
        .execute()
        .data
    )
    saved = dict(row.get("onboarding_steps") or {})
    saved[step] = "skipped"
    sb.table("users").update(
        {"onboarding_steps": saved},
    ).eq("id", user.id).execute()

    row["onboarding_steps"] = saved
    steps = _compute_steps(row)
    done = sum(1 for s in steps if s.completed)
    progress = int(done / len(steps) * 100) if steps else 0
    return OnboardingStatusResponse(steps=steps, progress=progress)


@router.post(
    "/complete",
    response_model=OnboardingCompleteResponse,
    summary="Mark Onboarding Complete",
)
async def complete_onboarding(
    user: CurrentUser,
) -> OnboardingCompleteResponse:
    sb = get_supabase()
    sb.table("users").update(
        {"onboarding_completed": True},
    ).eq("id", user.id).execute()
    return OnboardingCompleteResponse(completed=True)
