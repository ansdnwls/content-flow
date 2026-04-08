"""Schedule API — recurring posts with timezone and optimal time recommendations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.errors import NotFoundError
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/schedules", tags=["Schedules"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class CreateScheduleRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "platform": "youtube",
                "recurrence": "daily",
                "tz": "KST",
                "post_id": None,
                "cron_expression": None,
            },
        },
    )

    platform: str = Field(description="Target platform")
    recurrence: str = Field(
        description="Recurrence type: once, daily, weekly, custom",
    )
    tz: str = Field(default="UTC", description="Timezone (KST, EST, JST, UTC, ...)")
    post_id: str | None = Field(default=None, description="Linked post ID")
    cron_expression: str | None = Field(
        default=None,
        description="Custom cron: 'HH:MM day1,day2' e.g. '14:00 mon,wed,fri'",
    )


class ScheduleResponse(BaseModel):
    id: str
    user_id: str
    post_id: str | None = None
    platform: str
    tz: str
    recurrence: str
    cron_expression: str | None = None
    next_run_at: str
    is_active: bool
    created_at: str
    updated_at: str


class ScheduleListResponse(BaseModel):
    data: list[ScheduleResponse]
    total: int
    page: int
    limit: int


class TimeRecommendationResponse(BaseModel):
    platform: str
    recommended_times: list[str]
    description: str


@router.post(
    "",
    response_model=ScheduleResponse,
    status_code=201,
    summary="Create Schedule",
    description="Register a recurring schedule with timezone support.",
)
async def create_schedule(
    req: CreateScheduleRequest,
    user: CurrentUser,
) -> ScheduleResponse:
    service = SchedulerService()
    schedule = await service.create_schedule(
        user_id=user.id,
        platform=req.platform,
        recurrence=req.recurrence,
        tz=req.tz,
        cron_expression=req.cron_expression,
        post_id=req.post_id,
    )
    return ScheduleResponse(**schedule)


@router.get(
    "",
    response_model=ScheduleListResponse,
    summary="List Schedules",
    description="List user's schedules with optional active filter.",
)
async def list_schedules(
    user: CurrentUser,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 50,
) -> ScheduleListResponse:
    service = SchedulerService()
    data, total = await service.list_schedules(
        user_id=user.id,
        is_active=is_active,
        page=page,
        limit=limit,
    )
    return ScheduleListResponse(
        data=[ScheduleResponse(**row) for row in data],
        total=total,
        page=page,
        limit=limit,
    )


@router.delete(
    "/{schedule_id}",
    summary="Delete Schedule",
    description="Deactivate a schedule.",
    responses=NOT_FOUND_ERROR,
)
async def delete_schedule(
    schedule_id: UUID,
    user: CurrentUser,
) -> dict:
    service = SchedulerService()
    deleted = await service.delete_schedule(str(schedule_id), user.id)
    if not deleted:
        raise NotFoundError("Schedule", str(schedule_id))
    return {"deleted": True, "id": str(schedule_id)}


@router.get(
    "/recommend",
    response_model=list[TimeRecommendationResponse],
    summary="Recommend Optimal Times",
    description="Get platform-specific optimal posting time recommendations.",
)
async def recommend_times(
    user: CurrentUser,
    platforms: str = Query(
        description="Comma-separated platforms (e.g. youtube,tiktok,instagram)",
    ),
    tz: str = Query(default="UTC", description="Timezone"),
) -> list[TimeRecommendationResponse]:
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    recs = SchedulerService.recommend_times(platform_list, tz)
    return [
        TimeRecommendationResponse(
            platform=r.platform,
            recommended_times=r.recommended_times,
            description=r.description,
        )
        for r in recs
    ]
