"""Workspace access helpers."""

from __future__ import annotations

from app.core.db import get_supabase
from app.core.errors import ForbiddenError, NotFoundError

WORKSPACE_ROLES = {"owner", "admin", "editor", "viewer"}


def get_workspace_record(workspace_id: str) -> dict:
    """Return a workspace row or raise NotFoundError."""
    sb = get_supabase()
    response = (
        sb.table("workspaces")
        .select("*")
        .eq("id", workspace_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    result_data = rows[0] if rows else None
    if not result_data:
        raise NotFoundError("Workspace", workspace_id)
    return result_data


def get_workspace_access(workspace_id: str, user_id: str) -> tuple[dict, str]:
    """Return the workspace row plus the caller's role."""
    workspace = get_workspace_record(workspace_id)
    if workspace["owner_id"] == user_id:
        return workspace, "owner"

    sb = get_supabase()
    _mem_response = (
        sb.table("workspace_members")
        .select("role")
        .eq("workspace_id", workspace_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    _mem_rows = getattr(_mem_response, "data", None) or []
    membership = _mem_rows[0] if _mem_rows else None
    if not membership:
        raise ForbiddenError("Workspace access denied")
    return workspace, membership.get("role", "viewer")


def require_workspace_role(
    workspace_id: str,
    user_id: str,
    *,
    allowed_roles: set[str],
) -> tuple[dict, str]:
    """Return workspace access details or raise ForbiddenError."""
    workspace, role = get_workspace_access(workspace_id, user_id)
    if role not in allowed_roles:
        raise ForbiddenError("Insufficient workspace permissions")
    return workspace, role


def resolve_workspace_id_for_user(
    user_id: str,
    *,
    requested_workspace_id: str | None,
    default_workspace_id: str | None,
    api_key_workspace_id: str | None,
) -> str | None:
    """Resolve the effective workspace for the request."""
    workspace_id = requested_workspace_id or api_key_workspace_id or default_workspace_id
    if workspace_id is None:
        return None

    if api_key_workspace_id and workspace_id != api_key_workspace_id:
        raise ForbiddenError("API key is scoped to a different workspace")

    get_workspace_access(workspace_id, user_id)
    return workspace_id
