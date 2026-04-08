"""API Keys management: create, list, rotate, and per-key audit log."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.audit import record_audit
from app.core.auth import build_api_key_record
from app.core.db import get_supabase
from app.core.errors import NotFoundError
from app.core.workspaces import get_workspace_access

router = APIRouter(prefix="/keys", tags=["API Keys"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

EXPIRATION_DAYS: dict[str, int | None] = {
    "90d": 90,
    "180d": 180,
    "never": None,
}

GRACE_PERIOD_HOURS = 24


class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    expires_in: Literal["90d", "180d", "never"] = "never"
    workspace_id: str | None = None


class KeyResponse(BaseModel):
    id: str
    workspace_id: str | None = None
    name: str
    key_preview: str
    is_active: bool
    expires_at: datetime | None = None
    rotated_from: str | None = None
    created_at: datetime
    updated_at: datetime


class CreatedKeyResponse(KeyResponse):
    raw_key: str = Field(description="Full API key — shown only once.")


class RotateKeyResponse(BaseModel):
    new_key: CreatedKeyResponse
    old_key_id: str
    old_key_deactivates_at: datetime


class KeyAuditEntry(BaseModel):
    id: str
    action: str
    resource: str
    ip: str | None = None
    user_agent: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class KeyAuditResponse(BaseModel):
    data: list[KeyAuditEntry]
    total: int
    page: int
    limit: int


class KeyListResponse(BaseModel):
    data: list[KeyResponse]
    total: int


def _compute_expires_at(expires_in: str) -> str | None:
    days = EXPIRATION_DAYS.get(expires_in)
    if days is None:
        return None
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def _get_key_for_user(key_id: str, user_id: str, workspace_id: str | None = None) -> dict:
    sb = get_supabase()
    query = sb.table("api_keys").select("*").eq("id", key_id).eq("user_id", user_id)
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    result = query.maybe_single().execute()
    if not result.data:
        raise NotFoundError("API Key", key_id)
    return result.data


@router.post(
    "",
    response_model=CreatedKeyResponse,
    status_code=201,
    summary="Create API Key",
    description="Issue a new API key with optional expiration.",
)
async def create_key(req: CreateKeyRequest, user: CurrentUser) -> CreatedKeyResponse:
    workspace_id = req.workspace_id or user.workspace_id
    if req.workspace_id is not None:
        get_workspace_access(req.workspace_id, user.id)

    issued, record = build_api_key_record(
        user_id=UUID(user.id),
        name=req.name,
    )
    record["expires_at"] = _compute_expires_at(req.expires_in)
    record["workspace_id"] = workspace_id

    sb = get_supabase()
    inserted = sb.table("api_keys").insert(record).execute().data[0]

    await record_audit(
        user_id=user.id,
        action="key.created",
        resource=f"api_keys/{inserted['id']}",
        metadata={"name": req.name, "expires_in": req.expires_in},
    )

    return CreatedKeyResponse(
        id=inserted["id"],
        workspace_id=inserted.get("workspace_id"),
        name=inserted["name"],
        key_preview=inserted["key_preview"],
        is_active=inserted["is_active"],
        expires_at=inserted.get("expires_at"),
        rotated_from=inserted.get("rotated_from"),
        created_at=inserted["created_at"],
        updated_at=inserted["updated_at"],
        raw_key=issued.raw_key,
    )


@router.get(
    "",
    response_model=KeyListResponse,
    summary="List API Keys",
    description="Returns all API keys for the authenticated user.",
)
async def list_keys(user: CurrentUser) -> KeyListResponse:
    sb = get_supabase()
    query = sb.table("api_keys").select("*", count="exact").eq("user_id", user.id)
    if user.workspace_id is not None:
        query = query.eq("workspace_id", user.workspace_id)
    result = query.order("created_at", desc=True).execute()
    keys = [
        KeyResponse(
            id=row["id"],
            workspace_id=row.get("workspace_id"),
            name=row["name"],
            key_preview=row["key_preview"],
            is_active=row["is_active"],
            expires_at=row.get("expires_at"),
            rotated_from=row.get("rotated_from"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in result.data
    ]
    return KeyListResponse(data=keys, total=result.count or 0)


@router.post(
    "/{key_id}/rotate",
    response_model=RotateKeyResponse,
    summary="Rotate API Key",
    description=(
        "Issues a new key and schedules the old one for deactivation "
        f"after a {GRACE_PERIOD_HOURS}-hour grace period."
    ),
    responses=NOT_FOUND_ERROR,
)
async def rotate_key(key_id: UUID, user: CurrentUser) -> RotateKeyResponse:
    old_key = await _get_key_for_user(str(key_id), user.id, user.workspace_id)

    deactivates_at = datetime.now(UTC) + timedelta(hours=GRACE_PERIOD_HOURS)

    sb = get_supabase()
    sb.table("api_keys").update({
        "expires_at": deactivates_at.isoformat(),
    }).eq("id", old_key["id"]).execute()

    issued, record = build_api_key_record(
        user_id=UUID(user.id),
        name=old_key["name"],
    )
    record["rotated_from"] = old_key["id"]
    record["expires_at"] = old_key.get("expires_at")
    record["workspace_id"] = old_key.get("workspace_id")

    inserted = sb.table("api_keys").insert(record).execute().data[0]

    await record_audit(
        user_id=user.id,
        action="key.rotated",
        resource=f"api_keys/{inserted['id']}",
        metadata={
            "old_key_id": old_key["id"],
            "grace_period_hours": GRACE_PERIOD_HOURS,
        },
    )

    new_key = CreatedKeyResponse(
        id=inserted["id"],
        workspace_id=inserted.get("workspace_id"),
        name=inserted["name"],
        key_preview=inserted["key_preview"],
        is_active=inserted["is_active"],
        expires_at=inserted.get("expires_at"),
        rotated_from=inserted.get("rotated_from"),
        created_at=inserted["created_at"],
        updated_at=inserted["updated_at"],
        raw_key=issued.raw_key,
    )

    return RotateKeyResponse(
        new_key=new_key,
        old_key_id=old_key["id"],
        old_key_deactivates_at=deactivates_at,
    )


@router.get(
    "/{key_id}/audit",
    response_model=KeyAuditResponse,
    summary="Get Key Audit Log",
    description="Returns the usage audit trail for a specific API key.",
    responses=NOT_FOUND_ERROR,
)
async def get_key_audit(
    key_id: UUID,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> KeyAuditResponse:
    await _get_key_for_user(str(key_id), user.id, user.workspace_id)

    sb = get_supabase()
    offset = (page - 1) * limit
    result = (
        sb.table("audit_logs")
        .select("*", count="exact")
        .eq("api_key_id", str(key_id))
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    entries = [
        KeyAuditEntry(
            id=row["id"],
            action=row["action"],
            resource=row["resource"],
            ip=row.get("ip"),
            user_agent=row.get("user_agent"),
            metadata=row.get("metadata", {}),
            created_at=row["created_at"],
        )
        for row in result.data
    ]

    return KeyAuditResponse(
        data=entries,
        total=result.count or 0,
        page=page,
        limit=limit,
    )
