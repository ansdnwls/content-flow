"""Admin dashboard API endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.core.admin_auth import get_admin_user
from app.core.audit import flush_audit_logs, record_audit
from app.services.admin_analytics import AdminAnalyticsService

router = APIRouter(prefix="/dashboard", tags=["Admin"])
AdminUser = Annotated[dict, Depends(get_admin_user)]
DateQuery = Annotated[date | None, Query()]
GrowthGranularity = Annotated[Literal["day", "week", "month"], Query()]
TopUsersLimit = Annotated[int, Query(ge=1, le=50)]
ChurnLimit = Annotated[int, Query(ge=1, le=50)]
InactivityDays = Annotated[int, Query(ge=1, le=30)]


class OverviewResponse(BaseModel):
    period_start: str
    period_end: str
    total_users: int
    active_users_dau: int
    active_users_mau: int
    new_signups: int
    revenue_this_month: float
    total_posts: int
    total_videos: int
    error_rate: float
    average_response_time_ms: float


class GrowthPoint(BaseModel):
    bucket: str
    signups: int
    revenue: float
    api_calls: int
    posts: int
    videos: int


class GrowthResponse(BaseModel):
    granularity: Literal["day", "week", "month"]
    period_start: str
    period_end: str
    points: list[GrowthPoint]


class TopUserEntry(BaseModel):
    user_id: str
    email: str | None = None
    plan: str
    api_calls: int
    posts: int
    videos: int
    total_usage: int


class TopUsersResponse(BaseModel):
    period_start: str
    period_end: str
    users: list[TopUserEntry]


class ChurnUserEntry(BaseModel):
    user_id: str
    email: str | None = None
    plan: str
    last_seen_at: str | None = None
    days_inactive: int
    current_period_usage: int
    previous_period_usage: int
    usage_drop_ratio: float
    risk_score: int
    reasons: list[str]


class ChurnResponse(BaseModel):
    period_end: str
    inactivity_days: int
    users: list[ChurnUserEntry]


def _service() -> AdminAnalyticsService:
    return AdminAnalyticsService()


async def _audit_admin_view(
    request: Request,
    admin: dict,
    *,
    action: str,
    resource: str,
    metadata: dict,
) -> None:
    await record_audit(
        user_id=admin["id"],
        action=action,
        resource=resource,
        ip=getattr(getattr(request, "client", None), "host", None),
        user_agent=request.headers.get("user-agent"),
        metadata=metadata,
    )
    await flush_audit_logs()


@router.get("/overview", response_model=OverviewResponse, summary="Admin Overview")
async def dashboard_overview(
    request: Request,
    admin: AdminUser,
    start_date: DateQuery = None,
    end_date: DateQuery = None,
) -> OverviewResponse:
    payload = await _service().get_overview(start_date=start_date, end_date=end_date)
    await _audit_admin_view(
        request,
        admin,
        action="admin.dashboard.overview.view",
        resource="admin/dashboard/overview",
        metadata={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    )
    return OverviewResponse(**payload)


@router.get("/growth", response_model=GrowthResponse, summary="Admin Growth Trends")
async def dashboard_growth(
    request: Request,
    admin: AdminUser,
    granularity: GrowthGranularity = "day",
    start_date: DateQuery = None,
    end_date: DateQuery = None,
) -> GrowthResponse:
    payload = await _service().get_growth(
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
    )
    await _audit_admin_view(
        request,
        admin,
        action="admin.dashboard.growth.view",
        resource="admin/dashboard/growth",
        metadata={
            "granularity": granularity,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    )
    return GrowthResponse(**payload)


@router.get("/top-users", response_model=TopUsersResponse, summary="Top Users")
async def dashboard_top_users(
    request: Request,
    admin: AdminUser,
    limit: TopUsersLimit = 50,
    start_date: DateQuery = None,
    end_date: DateQuery = None,
) -> TopUsersResponse:
    payload = await _service().get_top_users(
        limit=limit,
        start_date=start_date,
        end_date=end_date,
    )
    await _audit_admin_view(
        request,
        admin,
        action="admin.dashboard.top_users.view",
        resource="admin/dashboard/top-users",
        metadata={
            "limit": limit,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    )
    return TopUsersResponse(**payload)


@router.get("/churn", response_model=ChurnResponse, summary="Churn Risk")
async def dashboard_churn(
    request: Request,
    admin: AdminUser,
    limit: ChurnLimit = 50,
    inactivity_days: InactivityDays = 7,
    end_date: DateQuery = None,
) -> ChurnResponse:
    payload = await _service().get_churn_risk(
        limit=limit,
        inactivity_days=inactivity_days,
        end_date=end_date,
    )
    await _audit_admin_view(
        request,
        admin,
        action="admin.dashboard.churn.view",
        resource="admin/dashboard/churn",
        metadata={
            "limit": limit,
            "inactivity_days": inactivity_days,
            "end_date": end_date.isoformat() if end_date else None,
        },
    )
    return ChurnResponse(**payload)
