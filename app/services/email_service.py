"""Email service using Resend SDK with template rendering and batch support."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Any

from app.config import get_settings
from app.core.db import get_supabase
from app.core.i18n import DEFAULT_LOCALE, normalize_locale

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

_resend = None


def _get_resend():
    """Lazy-load resend SDK."""
    global _resend  # noqa: PLW0603
    if _resend is None:
        if importlib.util.find_spec("resend") is None:
            msg = "resend package is not installed"
            raise RuntimeError(msg)
        import resend

        resend.api_key = get_settings().resend_api_key
        _resend = resend
    return _resend


def _resolve_template_path(template_name: str, ext: str, locale: str | None = None) -> Path | None:
    """Find a template file, preferring the locale-specific version."""
    loc = normalize_locale(locale)
    # Try locale-specific first, then fallback to root templates dir
    localized = TEMPLATES_DIR / loc / f"{template_name}.{ext}"
    if localized.exists():
        return localized
    fallback = TEMPLATES_DIR / f"{template_name}.{ext}"
    if fallback.exists():
        return fallback
    # Try default locale
    default = TEMPLATES_DIR / DEFAULT_LOCALE / f"{template_name}.{ext}"
    return default if default.exists() else None


def render_template(
    template_name: str, variables: dict[str, Any], locale: str | None = None,
) -> str:
    """Render an HTML email template with variable substitution."""
    path = _resolve_template_path(template_name, "html", locale)
    if path is None:
        msg = f"Email template '{template_name}' not found"
        raise FileNotFoundError(msg)
    raw = path.read_text(encoding="utf-8")
    return Template(raw).safe_substitute(variables)


def render_text(
    template_name: str, variables: dict[str, Any], locale: str | None = None,
) -> str | None:
    """Render plain-text version if it exists."""
    path = _resolve_template_path(template_name, "txt", locale)
    if path is None:
        return None
    raw = path.read_text(encoding="utf-8")
    return Template(raw).safe_substitute(variables)


def _log_email(
    user_id: str,
    to: str,
    subject: str,
    template: str | None,
    status: str,
    error: str | None = None,
) -> None:
    sb = get_supabase()
    sb.table("email_logs").insert({
        "user_id": user_id,
        "to_email": to,
        "subject": subject,
        "template": template,
        "status": status,
        "error": error,
        "sent_at": datetime.now(UTC).isoformat() if status == "sent" else None,
    }).execute()


async def send_email(
    *,
    user_id: str,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    tags: list[dict[str, str]] | None = None,
    template: str | None = None,
) -> dict[str, Any]:
    """Send a single email via Resend."""
    settings = get_settings()
    resend = _get_resend()

    params: dict[str, Any] = {
        "from_": f"{settings.email_from_name} <{settings.email_from}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "reply_to": settings.email_reply_to,
    }
    if text:
        params["text"] = text
    if tags:
        params["tags"] = tags

    try:
        result = resend.Emails.send(params)
        _log_email(user_id, to, subject, template, "sent")
        email_id = result.get("id") if isinstance(result, dict) else str(result)
        return {"status": "sent", "id": email_id}
    except Exception as exc:
        _log_email(user_id, to, subject, template, "failed", str(exc))
        return {"status": "failed", "error": str(exc)}


async def send_template(
    *,
    user_id: str,
    template_name: str,
    to: str,
    subject: str,
    variables: dict[str, Any],
    locale: str | None = None,
) -> dict[str, Any]:
    """Render and send a template-based email with locale support."""
    settings = get_settings()
    base_vars = {
        "dashboard_url": settings.email_dashboard_url,
        "docs_url": settings.email_docs_url,
        "unsubscribe_url": f"{settings.email_unsubscribe_base}?email={to}",
        "support_email": settings.email_reply_to,
        **variables,
    }
    html = render_template(template_name, base_vars, locale=locale)
    text = render_text(template_name, base_vars, locale=locale)
    return await send_email(
        user_id=user_id,
        to=to,
        subject=subject,
        html=html,
        text=text,
        template=template_name,
    )


async def send_batch(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Send up to 100 emails. Each dict needs: user_id, to, subject, html."""
    results = []
    for msg in messages[:100]:
        result = await send_email(**msg)
        results.append(result)
    return results
