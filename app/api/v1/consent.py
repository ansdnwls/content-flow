"""Consent management API — GDPR Art. 7 explicit consent tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.audit import record_audit
from app.core.db import get_supabase

router = APIRouter(
    prefix="/consent",
    tags=["Consent (GDPR)"],
    responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

CURRENT_CONSENT_VERSION = "2026-04"

VALID_PURPOSES = frozenset({
    "essential",
    "analytics",
    "marketing",
    "third_party_sharing",
    "cookies_functional",
    "cookies_analytics",
})
PURPOSE_ORDER = (
    "essential",
    "analytics",
    "marketing",
    "third_party_sharing",
    "cookies_functional",
    "cookies_analytics",
)


# -- Models -----------------------------------------------------------------


class ConsentStatus(BaseModel):
    purpose: str
    granted: bool
    granted_at: str | None = None
    revoked_at: str | None = None
    version: str = CURRENT_CONSENT_VERSION


class ConsentListResponse(BaseModel):
    consents: list[ConsentStatus]


class ConsentGrantRequest(BaseModel):
    purposes: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Purposes to grant consent for.",
    )


class ConsentRevokeRequest(BaseModel):
    purposes: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Purposes to revoke consent for.",
    )


class ConsentActionResponse(BaseModel):
    message: str
    updated: list[str]


class ConsentHistoryEntry(BaseModel):
    purpose: str
    granted: bool
    granted_at: str | None = None
    revoked_at: str | None = None
    ip: str | None = None
    version: str = CURRENT_CONSENT_VERSION


class ConsentHistoryResponse(BaseModel):
    history: list[ConsentHistoryEntry]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _validate_purposes(purposes: list[str]) -> list[str]:
    invalid = sorted({purpose for purpose in purposes if purpose not in VALID_PURPOSES})
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid consent purposes: {', '.join(invalid)}",
        )
    return list(dict.fromkeys(purposes))


def _ensure_essential_consent(
    sb,
    *,
    user_id: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    existing = (
        sb.table("consents")
        .select("id")
        .eq("user_id", user_id)
        .eq("purpose", "essential")
        .maybe_single()
        .execute()
    )
    if existing.data:
        return

    sb.table("consents").insert({
        "user_id": user_id,
        "purpose": "essential",
        "granted": True,
        "granted_at": _now_iso(),
        "ip": ip,
        "user_agent": user_agent,
        "version": CURRENT_CONSENT_VERSION,
    }).execute()


def _list_current_consents(sb, *, user_id: str) -> list[dict]:
    rows = (
        sb.table("consents")
        .select("purpose, granted, granted_at, revoked_at, version")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    current_by_purpose = {row["purpose"]: row for row in rows}
    current: list[dict] = []
    for purpose in PURPOSE_ORDER:
        row = current_by_purpose.get(
            purpose,
            {
                "purpose": purpose,
                "granted": purpose == "essential",
                "granted_at": None,
                "revoked_at": None,
                "version": CURRENT_CONSENT_VERSION,
            },
        )
        current.append(row)
    return current


# -- Endpoints --------------------------------------------------------------


@router.get(
    "",
    response_model=ConsentListResponse,
    summary="Get current consent status",
)
async def get_consents(user: CurrentUser) -> ConsentListResponse:
    """Return current consent state for the authenticated user."""
    sb = get_supabase()
    _ensure_essential_consent(sb, user_id=user.id)
    return ConsentListResponse(
        consents=[ConsentStatus(**row) for row in _list_current_consents(sb, user_id=user.id)],
    )


@router.post(
    "/grant",
    response_model=ConsentActionResponse,
    summary="Grant consent",
)
async def grant_consent(
    body: ConsentGrantRequest,
    user: CurrentUser,
    request: Request,
) -> ConsentActionResponse:
    """Grant consent for specified purposes."""
    sb = get_supabase()
    purposes = _validate_purposes(body.purposes)
    now_iso = _now_iso()
    client_ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    updated: list[str] = []
    _ensure_essential_consent(sb, user_id=user.id, ip=client_ip, user_agent=ua)

    for purpose in purposes:
        if purpose == "essential":
            continue

        existing = (
            sb.table("consents")
            .select("id")
            .eq("user_id", user.id)
            .eq("purpose", purpose)
            .maybe_single()
            .execute()
        )

        if existing.data:
            sb.table("consents").update({
                "granted": True,
                "granted_at": now_iso,
                "revoked_at": None,
                "ip": client_ip,
                "user_agent": ua,
                "version": CURRENT_CONSENT_VERSION,
            }).eq("id", existing.data["id"]).execute()
        else:
            sb.table("consents").insert({
                "user_id": user.id,
                "purpose": purpose,
                "granted": True,
                "granted_at": now_iso,
                "ip": client_ip,
                "user_agent": ua,
                "version": CURRENT_CONSENT_VERSION,
            }).execute()
        updated.append(purpose)

    await record_audit(
        user_id=user.id,
        action="consent.grant",
        resource="consent",
        ip=client_ip,
        metadata={"purposes": updated},
    )

    return ConsentActionResponse(
        message="Consent granted.",
        updated=updated,
    )


@router.post(
    "/revoke",
    response_model=ConsentActionResponse,
    summary="Revoke consent",
)
async def revoke_consent(
    body: ConsentRevokeRequest,
    user: CurrentUser,
    request: Request,
) -> ConsentActionResponse:
    """Revoke consent for specified purposes. 'essential' cannot be revoked."""
    sb = get_supabase()
    purposes = _validate_purposes(body.purposes)
    now_iso = _now_iso()
    client_ip = _client_ip(request)
    updated: list[str] = []
    _ensure_essential_consent(sb, user_id=user.id, ip=client_ip)

    for purpose in purposes:
        if purpose == "essential":
            continue

        existing = (
            sb.table("consents")
            .select("id")
            .eq("user_id", user.id)
            .eq("purpose", purpose)
            .maybe_single()
            .execute()
        )

        if existing.data:
            sb.table("consents").update({
                "granted": False,
                "revoked_at": now_iso,
                "version": CURRENT_CONSENT_VERSION,
            }).eq("id", existing.data["id"]).execute()
        else:
            sb.table("consents").insert({
                "user_id": user.id,
                "purpose": purpose,
                "granted": False,
                "revoked_at": now_iso,
                "ip": client_ip,
                "version": CURRENT_CONSENT_VERSION,
            }).execute()
        updated.append(purpose)

    await record_audit(
        user_id=user.id,
        action="consent.revoke",
        resource="consent",
        ip=client_ip,
        metadata={"purposes": updated},
    )

    return ConsentActionResponse(
        message="Consent revoked.",
        updated=updated,
    )


@router.get(
    "/history",
    response_model=ConsentHistoryResponse,
    summary="Consent change history",
)
async def get_consent_history(user: CurrentUser) -> ConsentHistoryResponse:
    """Return full consent change history for audit purposes."""
    sb = get_supabase()
    _ensure_essential_consent(sb, user_id=user.id)
    result = (
        sb.table("consents")
        .select("purpose, granted, granted_at, revoked_at, ip, version")
        .eq("user_id", user.id)
        .order("updated_at", desc=True)
        .execute()
    )
    return ConsentHistoryResponse(
        history=[ConsentHistoryEntry(**row) for row in result.data],
    )
