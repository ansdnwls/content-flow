"""Audit Log API — query user audit trail with filters and pagination."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.db import get_supabase

router = APIRouter(prefix="/audit", tags=["Audit"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class AuditLogEntry(BaseModel):
    id: str
    user_id: str
    api_key_id: str | None = None
    action: str
    resource: str
    ip: str | None = None
    user_agent: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class AuditLogResponse(BaseModel):
    data: list[AuditLogEntry]
    total: int
    page: int
    limit: int


@router.get(
    "",
    response_model=AuditLogResponse,
    summary="List Audit Logs",
    description=(
        "Returns the authenticated user's audit trail. "
        "Supports filtering by action, resource, and date range."
    ),
)
async def list_audit_logs(
    user: CurrentUser,
    action: Annotated[
        str | None,
        Query(description="Filter by action (e.g. key.created)"),
    ] = None,
    resource: Annotated[
        str | None,
        Query(description="Filter by resource prefix"),
    ] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogResponse:
    sb = get_supabase()
    query = (
        sb.table("audit_logs")
        .select("*", count="exact")
        .eq("user_id", user.id)
    )

    if action:
        query = query.eq("action", action)
    if resource:
        query = query.eq("resource", resource)
    if since:
        query = query.gte("created_at", since.isoformat())
    if until:
        query = query.lte("created_at", until.isoformat())

    offset = (page - 1) * limit
    result = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    entries = [
        AuditLogEntry(
            id=row["id"],
            user_id=row["user_id"],
            api_key_id=row.get("api_key_id"),
            action=row["action"],
            resource=row["resource"],
            ip=row.get("ip"),
            user_agent=row.get("user_agent"),
            metadata=row.get("metadata", {}),
            created_at=row["created_at"],
        )
        for row in result.data
    ]

    return AuditLogResponse(
        data=entries,
        total=result.count or 0,
        page=page,
        limit=limit,
    )
