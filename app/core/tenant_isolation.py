"""Tenant isolation helpers — enforce user_id scoping on DB queries."""
from __future__ import annotations

from typing import Any


class TenantViolationError(Exception):
    """Raised when a query would access data outside the user's tenant scope."""

    def __init__(self, resource: str, resource_id: str) -> None:
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(
            f"Tenant violation: {resource} '{resource_id}' "
            "does not belong to the current user"
        )


def require_owner(
    row: dict[str, Any] | None,
    user_id: str,
    *,
    resource: str,
    resource_id: str,
    owner_field: str = "user_id",
) -> dict[str, Any]:
    """Verify that *row* belongs to *user_id* or raise.

    Returns the row unchanged for chaining convenience.
    Raises 404-style TenantViolationError if row is None or owner mismatch.
    """
    if row is None:
        raise TenantViolationError(resource, resource_id)
    if row.get(owner_field) != user_id:
        raise TenantViolationError(resource, resource_id)
    return row


def require_owner_or_workspace(
    row: dict[str, Any] | None,
    user_id: str,
    workspace_id: str | None,
    *,
    resource: str,
    resource_id: str,
    owner_field: str = "owner_id",
) -> dict[str, Any]:
    """Like require_owner but also accepts workspace-level access.

    Matches if the row's owner matches user_id, OR if both the row and
    the caller share the same workspace_id.
    """
    if row is None:
        raise TenantViolationError(resource, resource_id)

    if row.get(owner_field) == user_id:
        return row

    row_workspace = row.get("workspace_id")
    if workspace_id and row_workspace and row_workspace == workspace_id:
        return row

    raise TenantViolationError(resource, resource_id)


def scoped_query(
    sb: Any,
    table: str,
    user_id: str,
    *,
    workspace_id: str | None = None,
    owner_field: str = "user_id",
) -> Any:
    """Return a Supabase query pre-filtered by user scope.

    If workspace_id is provided AND the table uses owner_id,
    the filter is on workspace_id instead (shared access).
    """
    q = sb.table(table).select("*")
    if workspace_id and owner_field == "owner_id":
        return q.eq("workspace_id", workspace_id)
    return q.eq(owner_field, user_id)
