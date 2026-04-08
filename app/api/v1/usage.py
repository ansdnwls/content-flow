"""Usage Dashboard API — monthly summary and daily usage history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.billing import get_usage_history, get_usage_summary
from app.core.cache import cache

router = APIRouter(prefix="/usage", tags=["Usage"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class UsageSummaryResponse(BaseModel):
    plan: str
    posts_used: int
    posts_limit: int
    videos_used: int
    videos_limit: int
    accounts_used: int
    accounts_limit: int
    rate_limit_per_minute: int


class DailyUsage(BaseModel):
    date: str
    posts: int
    videos: int


class UsageHistoryResponse(BaseModel):
    data: list[DailyUsage]
    days: int = Field(description="Number of days in the history window")


@router.get(
    "",
    response_model=UsageSummaryResponse,
    summary="Get Usage Summary",
    description="Returns the current month's usage summary including limits for your plan.",
)
@cache(ttl=60, key_prefix="usage-summary")
async def usage_summary(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> UsageSummaryResponse:
    summary = await get_usage_summary(user.id, user.plan, user.workspace_id)
    return UsageSummaryResponse(**summary)


@router.get(
    "/history",
    response_model=UsageHistoryResponse,
    summary="Get Usage History",
    description="Returns daily usage counts for the last N days (default 30).",
)
async def usage_history(
    user: CurrentUser,
    days: int = Query(30, ge=1, le=90, description="Number of days to look back"),
) -> UsageHistoryResponse:
    history = await get_usage_history(user.id, days=days, workspace_id=user.workspace_id)
    return UsageHistoryResponse(
        data=[DailyUsage(**entry) for entry in history],
        days=days,
    )
