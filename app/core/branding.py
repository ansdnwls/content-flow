"""White-label branding helpers."""

from __future__ import annotations

from string import Template

from app.core.db import get_supabase

DEFAULT_BRANDING = {
    "logo_url": None,
    "primary_color": "#0f172a",
    "font": "system-ui",
    "support_email": "support@contentflow.dev",
}


def get_workspace_branding(workspace_id: str) -> dict:
    """Return the workspace branding merged with defaults."""
    sb = get_supabase()
    workspace = (
        sb.table("workspaces")
        .select("id, name, branding, support_email")
        .eq("id", workspace_id)
        .maybe_single()
        .execute()
        .data
    )
    if not workspace:
        return dict(DEFAULT_BRANDING)

    branding = dict(DEFAULT_BRANDING)
    branding.update(workspace.get("branding") or {})
    if workspace.get("support_email"):
        branding["support_email"] = workspace["support_email"]
    branding["workspace_name"] = workspace.get("name")
    return branding


def render_email_template(template: str, workspace: dict, context: dict) -> str:
    """Render a lightweight branded email body."""
    branding = dict(DEFAULT_BRANDING)
    branding.update(workspace.get("branding") or {})
    payload = {
        **branding,
        "workspace_name": workspace.get("name", "Workspace"),
        **context,
    }
    return Template(template).safe_substitute(payload)


def render_webhook_payload(event: str, workspace: dict, data: dict) -> dict:
    """Apply workspace branding metadata to outbound webhook payloads."""
    branding = dict(DEFAULT_BRANDING)
    branding.update(workspace.get("branding") or {})
    return {
        "event": event,
        "from_brand": workspace.get("name"),
        "branding": branding,
        "data": data,
    }
