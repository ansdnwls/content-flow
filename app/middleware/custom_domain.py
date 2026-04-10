"""Custom domain resolution helpers for white-label workspaces."""

from __future__ import annotations

import secrets
import subprocess

from app.core.db import get_supabase


def normalize_host(host: str) -> str:
    """Normalize an incoming host header."""
    return host.split(":", 1)[0].strip().lower()


def generate_domain_verification_token() -> str:
    """Return a stable verification token format."""
    return f"cf-verify-{secrets.token_urlsafe(18)}"


def resolve_workspace_by_host(host: str) -> dict | None:
    """Resolve the workspace associated with a custom host."""
    normalized = normalize_host(host)
    if not normalized:
        return None
    sb = get_supabase()
    response = (
        sb.table("workspaces")
        .select("*")
        .eq("custom_domain", normalized)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None


def verify_custom_domain_record(domain: str, token: str) -> bool:
    """Best-effort TXT verification using nslookup."""
    txt_record = f"_contentflow-verify.{normalize_host(domain)}"
    try:
        result = subprocess.run(
            ["nslookup", "-type=TXT", txt_record],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    output = f"{result.stdout}\n{result.stderr}"
    return token in output
