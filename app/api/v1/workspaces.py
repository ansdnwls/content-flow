"""Workspace and white-label management APIs."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.db import get_supabase
from app.core.workspaces import get_workspace_access, require_workspace_role
from app.middleware.custom_domain import generate_domain_verification_token, normalize_host

router = APIRouter(prefix="/workspaces", tags=["Workspaces"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "workspace"


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str | None = None
    branding: dict = Field(default_factory=dict)
    support_email: str | None = None
    white_label_enabled: bool = False


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = None
    support_email: str | None = None
    white_label_enabled: bool | None = None


class BrandingRequest(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None
    font: str | None = None
    support_email: str | None = None


class DomainRequest(BaseModel):
    custom_domain: str = Field(..., min_length=3)


class WorkspaceResponse(BaseModel):
    id: str
    owner_id: str
    role: str
    name: str
    slug: str
    branding: dict = Field(default_factory=dict)
    support_email: str | None = None
    custom_domain: str | None = None
    white_label_enabled: bool = False
    domain_verification_token: str | None = None
    domain_verified_at: str | None = None
    created_at: str
    updated_at: str


class WorkspaceListResponse(BaseModel):
    data: list[WorkspaceResponse]
    total: int


def _serialize_workspace(row: dict, role: str) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=row["id"],
        owner_id=row["owner_id"],
        role=role,
        name=row["name"],
        slug=row["slug"],
        branding=row.get("branding") or {},
        support_email=row.get("support_email"),
        custom_domain=row.get("custom_domain"),
        white_label_enabled=row.get("white_label_enabled", False),
        domain_verification_token=row.get("domain_verification_token"),
        domain_verified_at=row.get("domain_verified_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

def _ensure_slug_available(slug: str, workspace_id: str | None = None) -> None:
    sb = get_supabase()
    response = sb.table("workspaces").select("id").eq("slug", slug).limit(1).execute()
    rows = getattr(response, "data", None) or []
    if rows and rows[0]["id"] != workspace_id:
        raise HTTPException(status_code=409, detail="Workspace slug is already in use")



@router.post("", response_model=WorkspaceResponse, status_code=201, summary="Create Workspace")
async def create_workspace(req: WorkspaceCreateRequest, user: CurrentUser) -> WorkspaceResponse:
    sb = get_supabase()
    slug = _slugify(req.slug or req.name)
    _ensure_slug_available(slug)

    inserted = (
        sb.table("workspaces")
        .insert(
            {
                "owner_id": user.id,
                "name": req.name,
                "slug": slug,
                "branding": req.branding,
                "support_email": req.support_email,
                "white_label_enabled": req.white_label_enabled,
            }
        )
        .execute()
        .data[0]
    )

    response = (
        sb.table("users")
        .select("default_workspace_id")
        .eq("id", user.id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    user_row = rows[0] if rows else None
    if user_row and user_row.get("default_workspace_id") is None:
        (
            sb.table("users")
            .update({"default_workspace_id": inserted["id"]})
            .eq("id", user.id)
            .execute()
        )

    return _serialize_workspace(inserted, "owner")


@router.get("", response_model=WorkspaceListResponse, summary="List Workspaces")
async def list_workspaces(user: CurrentUser) -> WorkspaceListResponse:
    sb = get_supabase()
    owned = sb.table("workspaces").select("*").eq("owner_id", user.id).execute().data
    memberships = (
        sb.table("workspace_members")
        .select("*")
        .eq("user_id", user.id)
        .execute()
        .data
    )

    seen: set[str] = set()
    items: list[WorkspaceResponse] = []
    for row in owned:
        seen.add(row["id"])
        items.append(_serialize_workspace(row, "owner"))

    for membership in memberships:
        workspace_id = membership["workspace_id"]
        if workspace_id in seen:
            continue
        workspace, _role = get_workspace_access(workspace_id, user.id)
        seen.add(workspace_id)
        items.append(_serialize_workspace(workspace, membership.get("role", "viewer")))

    return WorkspaceListResponse(data=items, total=len(items))


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get Workspace",
    responses=NOT_FOUND_ERROR,
)
async def get_workspace(workspace_id: str, user: CurrentUser) -> WorkspaceResponse:
    workspace, role = get_workspace_access(workspace_id, user.id)
    return _serialize_workspace(workspace, role)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update Workspace",
    responses=NOT_FOUND_ERROR,
)
async def update_workspace(
    workspace_id: str,
    req: WorkspaceUpdateRequest,
    user: CurrentUser,
) -> WorkspaceResponse:
    workspace, _role = require_workspace_role(
        workspace_id,
        user.id,
        allowed_roles={"owner", "admin"},
    )

    updates = req.model_dump(exclude_none=True)
    if "slug" in updates:
        updates["slug"] = _slugify(updates["slug"])
        _ensure_slug_available(updates["slug"], workspace_id)
    if not updates:
        role = "owner" if workspace["owner_id"] == user.id else "admin"
        return _serialize_workspace(workspace, role)

    sb = get_supabase()
    updated = sb.table("workspaces").update(updates).eq("id", workspace_id).single().execute().data
    role = "owner" if updated["owner_id"] == user.id else "admin"
    return _serialize_workspace(updated, role)


@router.delete("/{workspace_id}", summary="Delete Workspace", responses=NOT_FOUND_ERROR)
async def delete_workspace(workspace_id: str, user: CurrentUser) -> dict[str, str]:
    workspace, _role = require_workspace_role(
        workspace_id,
        user.id,
        allowed_roles={"owner"},
    )
    sb = get_supabase()
    sb.table("workspace_members").delete().eq("workspace_id", workspace_id).execute()
    for table_name in ("api_keys", "social_accounts", "posts", "video_jobs"):
        (
            sb.table(table_name)
            .update({"workspace_id": None})
            .eq("workspace_id", workspace_id)
            .execute()
        )
    (
        sb.table("users")
        .update({"default_workspace_id": None})
        .eq("default_workspace_id", workspace_id)
        .execute()
    )
    sb.table("workspaces").delete().eq("id", workspace_id).execute()
    return {"status": "deleted", "workspace_id": workspace["id"]}


@router.post(
    "/{workspace_id}/branding",
    response_model=WorkspaceResponse,
    summary="Update Branding",
    responses=NOT_FOUND_ERROR,
)
async def update_branding(
    workspace_id: str,
    req: BrandingRequest,
    user: CurrentUser,
) -> WorkspaceResponse:
    workspace, role = require_workspace_role(
        workspace_id,
        user.id,
        allowed_roles={"owner", "admin"},
    )
    branding = dict(workspace.get("branding") or {})
    updates = req.model_dump(exclude_none=True)
    support_email = updates.pop("support_email", workspace.get("support_email"))
    branding.update(updates)

    sb = get_supabase()
    updated = (
        sb.table("workspaces")
        .update({"branding": branding, "support_email": support_email})
        .eq("id", workspace_id)
        .single()
        .execute()
        .data
    )
    return _serialize_workspace(updated, role)


@router.post(
    "/{workspace_id}/domain",
    response_model=WorkspaceResponse,
    summary="Set Custom Domain",
    responses=NOT_FOUND_ERROR,
)
async def set_custom_domain(
    workspace_id: str,
    req: DomainRequest,
    user: CurrentUser,
) -> WorkspaceResponse:
    _workspace, role = require_workspace_role(
        workspace_id,
        user.id,
        allowed_roles={"owner", "admin"},
    )
    domain = normalize_host(req.custom_domain)
    token = generate_domain_verification_token()
    sb = get_supabase()
    updated = (
        sb.table("workspaces")
        .update(
            {
                "custom_domain": domain,
                "white_label_enabled": True,
                "domain_verification_token": token,
                "domain_verified_at": None,
            }
        )
        .eq("id", workspace_id)
        .single()
        .execute()
        .data
    )
    return _serialize_workspace(updated, role)
