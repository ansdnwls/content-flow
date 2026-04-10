"""Workspace member management APIs."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.db import get_supabase
from app.core.errors import ForbiddenError, NotFoundError
from app.core.workspaces import get_workspace_access, require_workspace_role

router = APIRouter(tags=["Workspace Members"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class InviteMemberRequest(BaseModel):
    user_id: str
    role: Literal["admin", "editor", "viewer"] = "viewer"


class UpdateMemberRequest(BaseModel):
    role: Literal["admin", "editor", "viewer"]


class MemberResponse(BaseModel):
    user_id: str
    workspace_id: str
    role: str
    email: str | None = None
    joined_at: str | None = None


class MemberListResponse(BaseModel):
    data: list[MemberResponse]
    total: int


def _user_or_404(user_id: str) -> dict:
    sb = get_supabase()
    response = sb.table("users").select("id, email").eq("id", user_id).limit(1).execute()
    rows = getattr(response, "data", None) or []
    user = rows[0] if rows else None
    if not user:
        raise NotFoundError("User", user_id)
    return user


@router.post(
    "/workspaces/{workspace_id}/members/invite",
    response_model=MemberResponse,
    status_code=201,
    summary="Invite Workspace Member",
    responses=NOT_FOUND_ERROR,
)
async def invite_member(
    workspace_id: str,
    req: InviteMemberRequest,
    user: CurrentUser,
) -> MemberResponse:
    require_workspace_role(workspace_id, user.id, allowed_roles={"owner"})
    invitee = _user_or_404(req.user_id)
    sb = get_supabase()
    response = (
        sb.table("workspace_members")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("user_id", req.user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    existing = rows[0] if rows else None
    if existing:
        updated = (
            sb.table("workspace_members")
            .update({"role": req.role, "invited_by": user.id})
            .eq("id", existing["id"])
            .single()
            .execute()
            .data
        )
        return MemberResponse(
            user_id=updated["user_id"],
            workspace_id=updated["workspace_id"],
            role=updated["role"],
            email=invitee.get("email"),
            joined_at=updated.get("joined_at"),
        )

    inserted = (
        sb.table("workspace_members")
        .insert(
            {
                "workspace_id": workspace_id,
                "user_id": req.user_id,
                "role": req.role,
                "invited_by": user.id,
            }
        )
        .execute()
        .data[0]
    )
    return MemberResponse(
        user_id=inserted["user_id"],
        workspace_id=inserted["workspace_id"],
        role=inserted["role"],
        email=invitee.get("email"),
        joined_at=inserted.get("joined_at"),
    )


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=MemberListResponse,
    summary="List Workspace Members",
    responses=NOT_FOUND_ERROR,
)
async def list_members(workspace_id: str, user: CurrentUser) -> MemberListResponse:
    workspace, role = get_workspace_access(workspace_id, user.id)
    sb = get_supabase()
    rows = (
        sb.table("workspace_members")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
        .data
    )

    users = {row["id"]: row for row in sb.table("users").select("id, email").execute().data}
    items = [
        MemberResponse(
            user_id=workspace["owner_id"],
            workspace_id=workspace_id,
            role="owner",
            email=users.get(workspace["owner_id"], {}).get("email"),
        )
    ]
    for row in rows:
        if row["user_id"] == workspace["owner_id"]:
            continue
        items.append(
            MemberResponse(
                user_id=row["user_id"],
                workspace_id=row["workspace_id"],
                role=row["role"],
                email=users.get(row["user_id"], {}).get("email"),
                joined_at=row.get("joined_at"),
            )
        )

    if role not in {"owner", "admin", "editor", "viewer"}:
        raise ForbiddenError("Workspace access denied")
    return MemberListResponse(data=items, total=len(items))


@router.patch(
    "/workspaces/{workspace_id}/members/{member_user_id}",
    response_model=MemberResponse,
    summary="Update Workspace Member Role",
    responses=NOT_FOUND_ERROR,
)
async def update_member(
    workspace_id: str,
    member_user_id: str,
    req: UpdateMemberRequest,
    user: CurrentUser,
) -> MemberResponse:
    require_workspace_role(workspace_id, user.id, allowed_roles={"owner"})
    sb = get_supabase()
    response = (
        sb.table("workspace_members")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("user_id", member_user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    membership = rows[0] if rows else None
    if not membership:
        raise NotFoundError("Workspace member", member_user_id)
    updated = (
        sb.table("workspace_members")
        .update({"role": req.role})
        .eq("id", membership["id"])
        .single()
        .execute()
        .data
    )
    member_user = _user_or_404(member_user_id)
    return MemberResponse(
        user_id=updated["user_id"],
        workspace_id=updated["workspace_id"],
        role=updated["role"],
        email=member_user.get("email"),
        joined_at=updated.get("joined_at"),
    )


@router.delete(
    "/workspaces/{workspace_id}/members/{member_user_id}",
    summary="Remove Workspace Member",
    responses=NOT_FOUND_ERROR,
)
async def remove_member(
    workspace_id: str,
    member_user_id: str,
    user: CurrentUser,
) -> dict[str, str]:
    workspace, _role = require_workspace_role(workspace_id, user.id, allowed_roles={"owner"})
    if member_user_id == workspace["owner_id"]:
        raise ForbiddenError("Cannot remove the workspace owner")

    sb = get_supabase()
    response = (
        sb.table("workspace_members")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("user_id", member_user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    membership = rows[0] if rows else None
    if not membership:
        raise NotFoundError("Workspace member", member_user_id)
    sb.table("workspace_members").delete().eq("id", membership["id"]).execute()
    return {"status": "removed", "user_id": member_user_id, "workspace_id": workspace_id}
