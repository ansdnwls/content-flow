"""Onboarding API — guides new users through setup steps."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.services.onboarding_service import (
    STEP_IDS,
    complete_step,
    get_next_action,
    get_progress,
    skip_remaining,
)

router = APIRouter(
    prefix="/onboarding", tags=["Onboarding"], responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class StepStatus(BaseModel):
    id: str
    title: str
    description: str
    optional: bool
    completed: bool
    completed_at: str | None = None
    data: dict[str, Any] | None = None


class OnboardingProgressResponse(BaseModel):
    steps: list[StepStatus]
    completed_count: int
    total_steps: int
    progress_pct: int
    all_complete: bool


class StepCompleteRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class NextActionResponse(BaseModel):
    step: str
    title: str
    description: str
    optional: bool
    hints: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/progress",
    response_model=OnboardingProgressResponse,
    summary="Get onboarding progress",
)
async def get_onboarding_progress(user: CurrentUser) -> OnboardingProgressResponse:
    """Return all steps with their completion status."""
    result = get_progress(user.id)
    return OnboardingProgressResponse(**result)


@router.post(
    "/steps/{step}/complete",
    response_model=OnboardingProgressResponse,
    summary="Complete an onboarding step",
)
async def complete_onboarding_step(
    step: str, user: CurrentUser, body: StepCompleteRequest | None = None,
) -> OnboardingProgressResponse:
    """Mark a specific onboarding step as completed."""
    if step not in STEP_IDS:
        raise HTTPException(status_code=422, detail=f"Unknown step: {step}")
    data = body.data if body else {}
    result = complete_step(user.id, step, data=data)
    return OnboardingProgressResponse(**result)


@router.post(
    "/skip",
    response_model=OnboardingProgressResponse,
    summary="Skip remaining onboarding steps",
)
async def skip_onboarding(user: CurrentUser) -> OnboardingProgressResponse:
    """Mark all remaining steps as skipped and complete onboarding."""
    result = skip_remaining(user.id)
    return OnboardingProgressResponse(**result)


@router.get(
    "/next-action",
    response_model=NextActionResponse | None,
    summary="Get recommended next step",
)
async def get_next_onboarding_action(user: CurrentUser) -> NextActionResponse | None:
    """Return the next incomplete step with hints, or null if all done."""
    result = get_next_action(user.id)
    if result is None:
        return None
    return NextActionResponse(**result)
