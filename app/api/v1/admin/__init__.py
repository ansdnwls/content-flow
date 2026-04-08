"""Admin Panel API for system management and monitoring endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.error_responses import COMMON_RESPONSES
from app.core.admin_auth import get_admin_user
from app.core.db import get_supabase
from app.workers.celery_app import celery_app

from . import feature_flags

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    responses={
        **COMMON_RESPONSES,
        403: {
            "description": "Admin access requires enterprise plan.",
            "content": {
                "application/json": {
                    "example": {"detail": "Admin access requires enterprise plan"},
                },
            },
        },
    },
)

AdminUser = Annotated[dict, Depends(get_admin_user)]


class UserSummary(BaseModel):
    id: str
    email: str
    plan: str
    is_active: bool
    created_at: str


class UserListResponse(BaseModel):
    data: list[UserSummary]
    total: int


class UserDetail(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    plan: str
    is_active: bool
    created_at: str
    posts_count: int = 0
    videos_count: int = 0
    accounts_count: int = 0


class PlanChangeRequest(BaseModel):
    plan: str = Field(
        description="Target plan: free, build, scale, enterprise",
        pattern="^(free|build|scale|enterprise)$",
    )


class PlanChangeResponse(BaseModel):
    user_id: str
    previous_plan: str
    new_plan: str


class SuspendRequest(BaseModel):
    reason: str = Field(default="", description="Reason for suspension")


class SystemStats(BaseModel):
    total_users: int
    active_users: int
    total_posts: int
    total_videos: int
    total_bombs: int
    total_webhooks: int
    plans: dict[str, int]


class CeleryJob(BaseModel):
    worker: str
    active_tasks: int
    scheduled_tasks: int


class JobsResponse(BaseModel):
    workers: list[CeleryJob]
    total_active: int
    total_scheduled: int


class HealthCheckResponse(BaseModel):
    supabase: bool
    redis: bool
    celery: bool
    status: str


@router.get("/users", response_model=UserListResponse, summary="List All Users")
async def list_users(
    admin: AdminUser,
    plan: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListResponse:
    sb = get_supabase()
    query = sb.table("users").select("id, email, plan, is_active, created_at", count="exact")
    if plan is not None:
        query = query.eq("plan", plan)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return UserListResponse(
        data=[UserSummary(**row) for row in result.data],
        total=result.count or len(result.data),
    )


@router.get("/users/{user_id}", response_model=UserDetail, summary="Get User Detail")
async def get_user_detail(user_id: str, admin: AdminUser) -> UserDetail:
    sb = get_supabase()
    user_result = (
        sb.table("users")
        .select("id, email, full_name, plan, is_active, created_at")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    user = user_result.data
    if not user:
        from app.core.errors import NotFoundError

        raise NotFoundError("User", user_id)

    posts_count = (
        sb.table("posts").select("id", count="exact").eq("owner_id", user_id).execute().count or 0
    )
    videos_count = (
        sb.table("video_jobs")
        .select("id", count="exact")
        .eq("owner_id", user_id)
        .execute()
        .count
        or 0
    )
    accounts_count = (
        sb.table("social_accounts")
        .select("id", count="exact")
        .eq("owner_id", user_id)
        .execute()
        .count
        or 0
    )

    return UserDetail(
        **user,
        posts_count=posts_count,
        videos_count=videos_count,
        accounts_count=accounts_count,
    )


@router.post("/users/{user_id}/plan", response_model=PlanChangeResponse, summary="Change User Plan")
async def change_user_plan(
    user_id: str,
    req: PlanChangeRequest,
    admin: AdminUser,
) -> PlanChangeResponse:
    sb = get_supabase()
    user_result = sb.table("users").select("id, plan").eq("id", user_id).maybe_single().execute()
    user = user_result.data
    if not user:
        from app.core.errors import NotFoundError

        raise NotFoundError("User", user_id)

    previous_plan = user["plan"]
    sb.table("users").update({"plan": req.plan}).eq("id", user_id).execute()

    return PlanChangeResponse(
        user_id=user_id,
        previous_plan=previous_plan,
        new_plan=req.plan,
    )


@router.post("/users/{user_id}/suspend", summary="Suspend User Account")
async def suspend_user(
    user_id: str,
    req: SuspendRequest,
    admin: AdminUser,
) -> dict[str, Any]:
    sb = get_supabase()
    user_result = (
        sb.table("users")
        .select("id, is_active")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    user = user_result.data
    if not user:
        from app.core.errors import NotFoundError

        raise NotFoundError("User", user_id)

    sb.table("users").update({"is_active": False}).eq("id", user_id).execute()
    sb.table("api_keys").update({"is_active": False}).eq("user_id", user_id).execute()

    return {"user_id": user_id, "status": "suspended", "reason": req.reason}


@router.get("/stats", response_model=SystemStats, summary="System Statistics")
async def system_stats(admin: AdminUser) -> SystemStats:
    sb = get_supabase()

    total_users = sb.table("users").select("id", count="exact").execute().count or 0
    active_users = (
        sb.table("users").select("id", count="exact").eq("is_active", True).execute().count or 0
    )
    total_posts = sb.table("posts").select("id", count="exact").execute().count or 0
    total_videos = sb.table("video_jobs").select("id", count="exact").execute().count or 0
    total_bombs = sb.table("bombs").select("id", count="exact").execute().count or 0
    total_webhooks = sb.table("webhooks").select("id", count="exact").execute().count or 0

    plan_rows = sb.table("users").select("plan").execute().data
    plans: dict[str, int] = {}
    for row in plan_rows:
        plan_name = row.get("plan", "free")
        plans[plan_name] = plans.get(plan_name, 0) + 1

    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        total_posts=total_posts,
        total_videos=total_videos,
        total_bombs=total_bombs,
        total_webhooks=total_webhooks,
        plans=plans,
    )


@router.get("/jobs", response_model=JobsResponse, summary="Celery Job Status")
async def celery_jobs(admin: AdminUser) -> JobsResponse:
    inspector = celery_app.control.inspect(timeout=2.0)

    active = inspector.active() or {}
    scheduled = inspector.scheduled() or {}

    workers: list[CeleryJob] = []
    total_active = 0
    total_scheduled = 0

    all_worker_names = set(active) | set(scheduled)
    for name in sorted(all_worker_names):
        active_count = len(active.get(name, []))
        scheduled_count = len(scheduled.get(name, []))
        total_active += active_count
        total_scheduled += scheduled_count
        workers.append(
            CeleryJob(
                worker=name,
                active_tasks=active_count,
                scheduled_tasks=scheduled_count,
            ),
        )

    return JobsResponse(
        workers=workers,
        total_active=total_active,
        total_scheduled=total_scheduled,
    )


@router.get("/health", response_model=HealthCheckResponse, summary="Full System Health Check")
async def admin_health_check(admin: AdminUser) -> HealthCheckResponse:
    from app.api.health import check_celery_ready, check_redis_ready, check_supabase_ready

    supabase_ok = False
    redis_ok = False
    celery_ok = False

    try:
        supabase_ok = await check_supabase_ready()
    except Exception:
        pass

    try:
        redis_ok = await check_redis_ready()
    except Exception:
        pass

    try:
        celery_ok = check_celery_ready()
    except Exception:
        pass

    all_ok = supabase_ok and redis_ok and celery_ok
    return HealthCheckResponse(
        supabase=supabase_ok,
        redis=redis_ok,
        celery=celery_ok,
        status="healthy" if all_ok else "degraded",
    )


class ComplianceDashboard(BaseModel):
    total_users: int
    consented_users: int
    pending_deletions: int
    completed_deletions: int
    export_requests_this_month: int
    recent_breaches: int
    dpa_signed_count: int


class PendingDeletion(BaseModel):
    user_id: str
    scheduled_for: str
    requested_at: str


class PendingDeletionsResponse(BaseModel):
    pending: list[PendingDeletion]


class ComplianceDataRequest(BaseModel):
    id: str
    user_id: str
    action: str
    resource: str
    created_at: str
    ip: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceDataRequestsResponse(BaseModel):
    requests: list[ComplianceDataRequest]


@router.get(
    "/compliance/dashboard",
    response_model=ComplianceDashboard,
    summary="Compliance Dashboard",
)
async def compliance_dashboard(admin: AdminUser) -> ComplianceDashboard:
    sb = get_supabase()

    total_users = sb.table("users").select("id", count="exact").execute().count or 0
    consented = (
        sb.table("consents")
        .select("user_id", count="exact")
        .eq("granted", True)
        .execute()
        .count
        or 0
    )
    pending_del = (
        sb.table("deletion_requests")
        .select("id", count="exact")
        .eq("status", "pending")
        .execute()
        .count
        or 0
    )
    completed_del = (
        sb.table("deletion_requests")
        .select("id", count="exact")
        .eq("status", "completed")
        .execute()
        .count
        or 0
    )
    breaches = sb.table("data_breaches").select("id", count="exact").execute().count or 0
    dpa_count = sb.table("dpa_signatures").select("id", count="exact").execute().count or 0
    export_logs = (
        sb.table("audit_logs")
        .select("id", count="exact")
        .eq("action", "privacy.export_request")
        .execute()
        .count
        or 0
    )

    return ComplianceDashboard(
        total_users=total_users,
        consented_users=consented,
        pending_deletions=pending_del,
        completed_deletions=completed_del,
        export_requests_this_month=export_logs,
        recent_breaches=breaches,
        dpa_signed_count=dpa_count,
    )


@router.get(
    "/compliance/pending-deletions",
    response_model=PendingDeletionsResponse,
    summary="Pending Deletion Requests",
)
async def pending_deletions(admin: AdminUser) -> PendingDeletionsResponse:
    sb = get_supabase()
    result = (
        sb.table("deletion_requests")
        .select("user_id, scheduled_for, requested_at")
        .eq("status", "pending")
        .order("scheduled_for")
        .execute()
    )
    return PendingDeletionsResponse(pending=[PendingDeletion(**row) for row in result.data])


@router.get(
    "/compliance/data-requests",
    response_model=ComplianceDataRequestsResponse,
    summary="Privacy Data Requests",
)
async def compliance_data_requests(
    admin: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> ComplianceDataRequestsResponse:
    sb = get_supabase()
    logs = sb.table("audit_logs").select(
        "id, user_id, action, resource, created_at, ip, metadata",
    ).execute().data

    privacy_actions = [
        row
        for row in logs
        if isinstance(row.get("action"), str) and row["action"].startswith("privacy.")
    ]
    privacy_actions.sort(key=lambda row: row.get("created_at", ""), reverse=True)

    return ComplianceDataRequestsResponse(
        requests=[ComplianceDataRequest(**row) for row in privacy_actions[:limit]],
    )


router.include_router(feature_flags.router)
