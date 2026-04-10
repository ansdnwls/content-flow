"""GDPR Data Rights API — Art. 15-21 user privacy endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.audit import record_audit
from app.core.db import get_supabase
from app.core.errors import NotFoundError
from app.services.billing_service import cancel_subscription
from app.services.data_export_service import (
    create_export_request,
    delete_export_artifacts,
    get_export_status,
    load_export_manifest,
    validate_download_token,
)
from app.workers.data_export_worker import generate_user_data_export_task

router = APIRouter(
    prefix="/privacy",
    tags=["Privacy (GDPR)"],
    responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

GRACE_PERIOD_DAYS = 14
EXPORT_LINK_TTL_HOURS = 24
OBJECTABLE_PURPOSES = frozenset({
    "analytics",
    "marketing",
    "third_party_sharing",
    "cookies_functional",
    "cookies_analytics",
})


# -- Response models --------------------------------------------------------


class UserDataResponse(BaseModel):
    profile: dict[str, Any]
    posts: list[dict[str, Any]] = Field(default_factory=list)
    posts_count: int
    video_jobs: list[dict[str, Any]] = Field(default_factory=list)
    video_jobs_count: int
    social_accounts: list[dict[str, Any]]
    analytics_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    payment_summary: dict[str, Any]
    audit_logs: list[dict[str, Any]] = Field(default_factory=list)
    audit_logs_count: int
    notification_preferences: dict[str, Any] = Field(default_factory=dict)
    consents: list[dict[str, Any]]


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)


class ProfileUpdateResponse(BaseModel):
    updated: bool
    fields: list[str]


class ExportResponse(BaseModel):
    export_id: str
    message: str
    status: str
    format: str
    requested_at: str
    expires_at: str
    encrypted: bool = False
    completed_at: str | None = None
    download_url: str | None = None
    status_url: str | None = None
    summary: dict[str, int] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    format: Literal["json", "zip"] = "json"
    encrypt: bool = False
    password: str | None = Field(default=None, min_length=8, max_length=128)


class DeletionResponse(BaseModel):
    message: str
    scheduled_for: str | None = None
    grace_period_days: int = GRACE_PERIOD_DAYS


class DeletionCancelResponse(BaseModel):
    message: str
    cancelled: bool


class RestrictionResponse(BaseModel):
    message: str
    restricted: bool


class ObjectionResponse(BaseModel):
    message: str
    objected_purposes: list[str]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _sanitize_social_account(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"encrypted_access_token", "encrypted_refresh_token"}
    }


def _get_notification_preferences(sb, user_id: str) -> dict[str, Any]:
    response = (
        sb.table("notification_preferences")
        .select(
            "product_updates, billing, security, monthly_summary, webhook_alerts",
        )
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else {}


def _upsert_notification_preferences(sb, user_id: str, updates: dict[str, Any]) -> None:
    current = _get_notification_preferences(sb, user_id)
    current.update({"user_id": user_id, **updates})
    sb.table("notification_preferences").upsert(
        current,
        on_conflict="user_id",
    ).execute()


def _build_export_bundle(user_id: str) -> dict[str, Any]:
    sb = get_supabase()
    user_row = (
        sb.table("users")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    posts = sb.table("posts").select("*").eq("owner_id", user_id).execute().data
    videos = sb.table("video_jobs").select("*").eq("owner_id", user_id).execute().data
    social_accounts = (
        sb.table("social_accounts")
        .select("*")
        .eq("owner_id", user_id)
        .execute()
        .data
    )
    analytics = (
        sb.table("analytics_snapshots")
        .select("*")
        .eq("owner_id", user_id)
        .execute()
        .data
    )
    payments = sb.table("payments").select("*").eq("user_id", user_id).execute().data
    audit_logs = sb.table("audit_logs").select("*").eq("user_id", user_id).execute().data
    notifications = _get_notification_preferences(sb, user_id)
    consents = sb.table("consents").select("*").eq("user_id", user_id).execute().data
    subscription_events = (
        sb.table("subscription_events")
        .select("*")
        .eq("user_id", user_id)
        .execute()
        .data
    )

    return {
        "profile": user_row,
        "posts": posts,
        "video_jobs": videos,
        "social_accounts": [_sanitize_social_account(row) for row in social_accounts],
        "analytics_snapshots": analytics,
        "payments": payments,
        "audit_logs": audit_logs,
        "notification_preferences": notifications,
        "consents": consents,
        "subscription_events": subscription_events,
    }


def _build_export_summary(bundle: dict[str, Any]) -> dict[str, int]:
    return {
        "posts": len(bundle["posts"]),
        "video_jobs": len(bundle["video_jobs"]),
        "social_accounts": len(bundle["social_accounts"]),
        "analytics_snapshots": len(bundle["analytics_snapshots"]),
        "payments": len(bundle["payments"]),
        "audit_logs": len(bundle["audit_logs"]),
        "consents": len(bundle["consents"]),
        "subscription_events": len(bundle["subscription_events"]),
    }


# -- Endpoints --------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserDataResponse,
    summary="Right to Access (Art. 15)",
)
async def get_my_data(user: CurrentUser, request: Request) -> UserDataResponse:
    """Return all personal data held for the authenticated user."""
    sb = get_supabase()

    user_row = (
        sb.table("users")
        .select("id, email, full_name, plan, is_active, created_at")
        .eq("id", user.id)
        .single()
        .execute()
    ).data

    posts = sb.table("posts").select("*").eq("owner_id", user.id).execute().data
    videos = sb.table("video_jobs").select("*").eq("owner_id", user.id).execute().data

    socials_raw = (
        sb.table("social_accounts")
        .select("*")
        .eq("owner_id", user.id)
        .execute()
    ).data
    socials = [_sanitize_social_account(row) for row in socials_raw]
    analytics = (
        sb.table("analytics_snapshots")
        .select("*")
        .eq("owner_id", user.id)
        .execute()
        .data
    )
    payments = sb.table("payments").select("*").eq("user_id", user.id).execute().data
    audits = (
        sb.table("audit_logs")
        .select("action, resource, created_at, ip, metadata")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    consents = (
        sb.table("consents")
        .select("purpose, granted, granted_at, revoked_at, version")
        .eq("user_id", user.id)
        .execute()
    ).data
    notification_preferences = _get_notification_preferences(sb, user.id)

    await record_audit(
        user_id=user.id,
        action="privacy.access",
        resource="privacy",
        ip=_client_ip(request),
    )

    return UserDataResponse(
        profile=user_row,
        posts=posts,
        posts_count=len(posts),
        video_jobs=videos,
        video_jobs_count=len(videos),
        social_accounts=socials,
        analytics_snapshots=analytics,
        payment_summary={
            "count": len(payments),
            "total_amount": sum(int(payment.get("amount", 0) or 0) for payment in payments),
            "currencies": sorted({payment.get("currency", "usd") for payment in payments}),
        },
        audit_logs=audits[:50],
        audit_logs_count=len(audits),
        notification_preferences=notification_preferences,
        consents=consents,
    )


@router.patch(
    "/me",
    response_model=ProfileUpdateResponse,
    summary="Right to Rectification (Art. 16)",
)
async def update_my_profile(
    body: ProfileUpdateRequest,
    user: CurrentUser,
    request: Request,
) -> ProfileUpdateResponse:
    """Allow user to correct personal data."""
    updates: dict[str, Any] = {}
    if body.full_name is not None:
        updates["full_name"] = body.full_name
    if body.email is not None:
        updates["email"] = body.email
        updates["email_verified"] = False
        updates["email_verified_at"] = None

    if not updates:
        return ProfileUpdateResponse(updated=False, fields=[])

    sb = get_supabase()
    sb.table("users").update(updates).eq("id", user.id).execute()

    await record_audit(
        user_id=user.id,
        action="privacy.rectify",
        resource="privacy",
        ip=request.client.host if request.client else None,
        metadata={"fields": list(updates.keys())},
    )

    return ProfileUpdateResponse(updated=True, fields=list(updates.keys()))


@router.post(
    "/export",
    response_model=ExportResponse,
    summary="Right to Data Portability (Art. 20)",
)
async def request_export(
    body: ExportRequest,
    user: CurrentUser,
    request: Request,
) -> ExportResponse:
    """Request a full data export. Returns status (async processing)."""
    if body.encrypt and not body.password:
        raise HTTPException(status_code=400, detail="password is required when encrypt=true")
    if body.password and not body.encrypt:
        raise HTTPException(status_code=400, detail="encrypt must be true when password is set")

    metadata = create_export_request(
        user.id,
        export_format=body.format,
        encrypted=body.encrypt,
        sb=get_supabase(),
    )
    generate_user_data_export_task.delay(
        metadata["export_id"],
        user.id,
        body.format,
        body.password,
    )

    await record_audit(
        user_id=user.id,
        action="privacy.export_request",
        resource="privacy",
        ip=_client_ip(request),
        metadata={
            "format": body.format,
            "summary": metadata["summary"],
            "export_id": metadata["export_id"],
            "encrypted": body.encrypt,
        },
    )
    return ExportResponse(
        message="Data export request received. You will be notified when ready.",
        status="queued",
        export_id=metadata["export_id"],
        format=body.format,
        requested_at=metadata["requested_at"],
        expires_at=metadata["expires_at"],
        encrypted=body.encrypt,
        status_url=f"{str(request.base_url).rstrip('/')}/api/v1/privacy/export/{metadata['export_id']}",
        summary=metadata["summary"],
    )


@router.get(
    "/export/{export_id}",
    response_model=ExportResponse,
    summary="Get data export status",
)
async def get_export_request_status(
    export_id: str,
    user: CurrentUser,
    request: Request,
) -> ExportResponse:
    try:
        status = get_export_status(
            export_id,
            user_id=user.id,
            base_url=str(request.base_url).rstrip("/"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Export not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    return ExportResponse(
        export_id=status["export_id"],
        message="Data export status retrieved.",
        status=status["status"],
        format=status["format"],
        requested_at=status["requested_at"],
        expires_at=status["expires_at"],
        encrypted=status["encrypted"],
        completed_at=status.get("completed_at"),
        download_url=status.get("download_url"),
        status_url=f"{str(request.base_url).rstrip('/')}/api/v1/privacy/export/{export_id}",
        summary=status["summary"],
    )


@router.get(
    "/export/{export_id}/download",
    summary="Download completed data export",
)
async def download_export(
    export_id: str,
    token: str,
    user: CurrentUser,
) -> FileResponse:
    manifest = load_export_manifest(export_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Export not found")
    if manifest["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        validate_download_token(export_id, user.id, token)
    except jwt.ExpiredSignatureError as exc:
        delete_export_artifacts(export_id)
        raise HTTPException(status_code=410, detail="Export link has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=403, detail="Invalid export token") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc

    file_path = manifest.get("file_path")
    if manifest.get("status") != "ready" or not file_path:
        raise HTTPException(status_code=409, detail="Export is not ready")

    path = file_path
    if not path:
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"{export_id}.zip",
        background=BackgroundTask(delete_export_artifacts, export_id),
    )


@router.delete(
    "/me",
    response_model=DeletionResponse,
    summary="Right to Erasure (Art. 17)",
)
async def request_deletion(
    user: CurrentUser,
    request: Request,
) -> DeletionResponse:
    """Request account deletion with 14-day grace period."""
    sb = get_supabase()

    response = (
        sb.table("deletion_requests")
        .select("id, status, scheduled_for")
        .eq("user_id", user.id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    existing = rows[0] if rows else None
    if existing:
        return DeletionResponse(
            message="Deletion already scheduled",
            scheduled_for=existing["scheduled_for"],
        )

    scheduled_for = datetime.now(UTC) + timedelta(days=GRACE_PERIOD_DAYS)

    sb.table("deletion_requests").insert({
        "user_id": user.id,
        "status": "pending",
        "requested_at": _now_iso(),
        "scheduled_for": scheduled_for.isoformat(),
    }).execute()

    sb.table("users").update({
        "is_active": False,
        "deletion_scheduled_at": scheduled_for.isoformat(),
    }).eq("id", user.id).execute()

    sb.table("api_keys").update({
        "is_active": False,
    }).eq("user_id", user.id).execute()
    sb.table("social_accounts").update({
        "status": "deletion_pending",
    }).eq("owner_id", user.id).execute()

    response = sb.table("users").select("stripe_subscription_id").eq("id", user.id).limit(1).execute()
    rows = getattr(response, "data", None) or []
    subscription_row = rows[0] if rows else None
    if subscription_row and subscription_row.get("stripe_subscription_id"):
        try:
            await cancel_subscription(user.id)
        except Exception:
            sb.table("users").update({
                "cancel_at_period_end": True,
            }).eq("id", user.id).execute()

    await record_audit(
        user_id=user.id,
        action="privacy.deletion_request",
        resource="privacy",
        ip=_client_ip(request),
    )

    return DeletionResponse(
        message=f"Account deletion scheduled. {GRACE_PERIOD_DAYS}-day grace period.",
        scheduled_for=scheduled_for.isoformat(),
    )


@router.post(
    "/cancel-deletion",
    response_model=DeletionCancelResponse,
    summary="Cancel pending deletion",
)
async def cancel_deletion(
    user: CurrentUser,
    request: Request,
) -> DeletionCancelResponse:
    """Cancel a pending deletion request within the grace period."""
    sb = get_supabase()

    response = (
        sb.table("deletion_requests")
        .select("id")
        .eq("user_id", user.id)
        .eq("status", "pending")
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    existing = rows[0] if rows else None
    if not existing:
        raise NotFoundError("deletion_request", user.id)

    sb.table("deletion_requests").update({
        "status": "cancelled",
    }).eq("id", existing["id"]).execute()

    sb.table("users").update({
        "is_active": True,
        "deletion_scheduled_at": None,
    }).eq("id", user.id).execute()

    sb.table("api_keys").update({
        "is_active": True,
    }).eq("user_id", user.id).execute()

    await record_audit(
        user_id=user.id,
        action="privacy.deletion_cancel",
        resource="privacy",
        ip=_client_ip(request),
    )

    return DeletionCancelResponse(
        message="Deletion cancelled. Account reactivated.",
        cancelled=True,
    )


@router.post(
    "/restrict",
    response_model=RestrictionResponse,
    summary="Right to Restriction (Art. 18)",
)
async def restrict_processing(
    user: CurrentUser,
    request: Request,
) -> RestrictionResponse:
    """Request restriction of data processing."""
    sb = get_supabase()
    sb.table("users").update({
        "data_processing_restricted": True,
    }).eq("id", user.id).execute()
    _upsert_notification_preferences(
        sb,
        user.id,
        {
            "product_updates": False,
            "monthly_summary": False,
            "webhook_alerts": False,
        },
    )

    await record_audit(
        user_id=user.id,
        action="privacy.restrict",
        resource="privacy",
        ip=_client_ip(request),
    )

    return RestrictionResponse(
        message="Data processing restricted.",
        restricted=True,
    )


@router.post(
    "/unrestrict",
    response_model=RestrictionResponse,
    summary="Lift processing restriction",
)
async def unrestrict_processing(
    user: CurrentUser,
    request: Request,
) -> RestrictionResponse:
    """Lift restriction of data processing."""
    sb = get_supabase()
    sb.table("users").update({
        "data_processing_restricted": False,
    }).eq("id", user.id).execute()

    await record_audit(
        user_id=user.id,
        action="privacy.unrestrict",
        resource="privacy",
        ip=_client_ip(request),
    )

    return RestrictionResponse(
        message="Data processing restriction lifted.",
        restricted=False,
    )


class ObjectionRequest(BaseModel):
    purposes: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Purposes to object to (e.g. analytics, marketing).",
    )


@router.post(
    "/object",
    response_model=ObjectionResponse,
    summary="Right to Object (Art. 21)",
)
async def object_processing(
    body: ObjectionRequest,
    user: CurrentUser,
    request: Request,
) -> ObjectionResponse:
    """Object to specific data processing purposes."""
    sb = get_supabase()
    invalid = sorted({purpose for purpose in body.purposes if purpose not in OBJECTABLE_PURPOSES})
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid objection purposes: {', '.join(invalid)}",
        )

    for purpose in body.purposes:
        response = (
            sb.table("consents")
            .select("id")
            .eq("user_id", user.id)
            .eq("purpose", purpose)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        existing = rows[0] if rows else None
        now_iso = _now_iso()
        if existing:
            sb.table("consents").update({
                "granted": False,
                "revoked_at": now_iso,
            }).eq("id", existing["id"]).execute()
        else:
            sb.table("consents").insert({
                "user_id": user.id,
                "purpose": purpose,
                "granted": False,
                "revoked_at": now_iso,
                "ip": _client_ip(request),
            }).execute()

    preference_updates: dict[str, Any] = {}
    if "marketing" in body.purposes:
        preference_updates["product_updates"] = False
    if {"analytics", "cookies_analytics"} & set(body.purposes):
        preference_updates["monthly_summary"] = False
    if preference_updates:
        _upsert_notification_preferences(sb, user.id, preference_updates)

    await record_audit(
        user_id=user.id,
        action="privacy.object",
        resource="privacy",
        ip=_client_ip(request),
        metadata={"purposes": body.purposes},
    )

    return ObjectionResponse(
        message="Objection recorded.",
        objected_purposes=body.purposes,
    )
