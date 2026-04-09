"""Optional Sentry initialization helpers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, Request

from app.config import Settings, get_settings
from app.core.errors import AuthenticationError, NotFoundError, RateLimitError

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - optional dependency
    sentry_sdk = None

try:  # pragma: no cover - optional dependency
    from sentry_sdk.integrations.celery import CeleryIntegration
except Exception:  # pragma: no cover - optional dependency
    CeleryIntegration = None

try:  # pragma: no cover - optional dependency
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except Exception:  # pragma: no cover - optional dependency
    FastApiIntegration = None

try:  # pragma: no cover - optional dependency
    from sentry_sdk.integrations.redis import RedisIntegration
except Exception:  # pragma: no cover - optional dependency
    RedisIntegration = None

try:  # pragma: no cover - optional dependency
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
except Exception:  # pragma: no cover - optional dependency
    SqlalchemyIntegration = None

SentryRuntime = Literal["web", "worker"]

_EMAIL_PATTERN = re.compile(r"([A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+)")
_PHONE_PATTERN = re.compile(r"(?<!\w)(\+?\d[\d\-\s().]{7,}\d)")
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]+")
_JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_\-.]+")
_SENSITIVE_KEYWORDS = {
    "api_key": "[masked-token]",
    "apikey": "[masked-token]",
    "authorization": "[masked-token]",
    "cookie": "[masked-token]",
    "dsn": "[masked-token]",
    "email": "[masked-email]",
    "password": "[masked-token]",
    "phone": "[masked-phone]",
    "secret": "[masked-token]",
    "token": "[masked-token]",
}
_IGNORED_STATUS_CODES = {401, 404, 429}


def _get_release_tag() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except Exception:
        return "unknown"
    release = result.stdout.strip()
    return release or "unknown"


def _get_environment(settings: Settings) -> str:
    return settings.sentry_environment or settings.app_env


def _build_integrations(runtime: SentryRuntime) -> list[Any]:
    integrations: list[Any] = []
    if runtime == "web" and FastApiIntegration is not None:
        integrations.append(FastApiIntegration())
    if CeleryIntegration is not None:
        integrations.append(CeleryIntegration())
    if RedisIntegration is not None:
        integrations.append(RedisIntegration())
    if SqlalchemyIntegration is not None:
        integrations.append(SqlalchemyIntegration())
    return integrations


def _set_scope_user(scope: Any, user: dict[str, str]) -> None:
    if hasattr(scope, "set_user"):
        scope.set_user(user)
        return
    scope.user = user


def _mask_string(value: str) -> str:
    masked = _EMAIL_PATTERN.sub("[masked-email]", value)
    masked = _PHONE_PATTERN.sub("[masked-phone]", masked)
    masked = _BEARER_PATTERN.sub("Bearer [masked-token]", masked)
    masked = _JWT_PATTERN.sub("[masked-token]", masked)
    return masked


def _masked_value_for_key(key: str) -> str | None:
    lowered = key.lower()
    for keyword, replacement in _SENSITIVE_KEYWORDS.items():
        if keyword in lowered:
            return replacement
    return None


def mask_pii(value: Any, *, key: str | None = None) -> Any:
    """Recursively mask known PII in Sentry payloads."""
    if key is not None:
        replacement = _masked_value_for_key(key)
        if replacement is not None:
            return replacement

    if isinstance(value, dict):
        return {
            item_key: mask_pii(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [mask_pii(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_pii(item) for item in value)
    if isinstance(value, str):
        return _mask_string(value)
    return value


def _should_ignore_event(event: dict[str, Any], hint: dict[str, Any] | None) -> bool:
    hint = hint or {}
    exc_info = hint.get("exc_info")
    if exc_info:
        exc = exc_info[1]
        if isinstance(exc, HTTPException) and exc.status_code in _IGNORED_STATUS_CODES:
            return True
        if isinstance(exc, (AuthenticationError, NotFoundError, RateLimitError)):
            return True

    request = event.get("request")
    if isinstance(request, dict):
        status_code = request.get("status_code")
        if str(status_code).isdigit() and int(status_code) in _IGNORED_STATUS_CODES:
            return True

    tags = event.get("tags")
    if isinstance(tags, dict):
        status_code = tags.get("http.status_code")
        if str(status_code).isdigit() and int(status_code) in _IGNORED_STATUS_CODES:
            return True

    return False


def before_send(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Filter noisy events and redact PII before sending them to Sentry."""
    if _should_ignore_event(event, hint):
        return None
    return mask_pii(event)


def init_sentry(
    settings: Settings | None = None,
    *,
    runtime: SentryRuntime = "web",
) -> bool:
    """Initialize Sentry when a DSN is configured and the SDK is installed."""
    settings = settings or get_settings()
    if not settings.sentry_dsn or sentry_sdk is None:
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=_get_environment(settings),
        release=_get_release_tag(),
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        before_send=before_send,
        ignore_errors=[AuthenticationError, NotFoundError, RateLimitError],
        integrations=_build_integrations(runtime),
    )

    if hasattr(sentry_sdk, "set_tag"):
        sentry_sdk.set_tag("runtime", runtime)
        sentry_sdk.set_tag("backend", "supabase")

    return True


def capture_event(
    event_type: str,
    data: dict[str, Any] | None = None,
    *,
    level: str = "info",
) -> str | None:
    """Capture a structured event when Sentry is enabled."""
    settings = get_settings()
    if sentry_sdk is None or settings.sentry_dsn is None:
        return None

    payload = {
        "message": event_type,
        "level": level,
        "tags": {"event_type": event_type},
        "extra": mask_pii(data or {}),
    }
    return sentry_sdk.capture_event(payload)


def set_user_context(user_id: str | None, email: str | None = None) -> None:
    """Set the active Sentry user context if Sentry is enabled."""
    settings = get_settings()
    if sentry_sdk is None or settings.sentry_dsn is None:
        return

    user: dict[str, str] = {}
    if user_id:
        user["id"] = user_id
    if email:
        user["email"] = email

    if hasattr(sentry_sdk, "set_user"):
        sentry_sdk.set_user(user or None)


def capture_sentry_exception(request: Request, exc: Exception) -> None:
    """Send an exception to Sentry when initialized."""
    settings = get_settings()
    if sentry_sdk is None or settings.sentry_dsn is None:
        return

    with sentry_sdk.push_scope() as scope:
        user_id = getattr(request.state, "user_id", None)
        api_key_prefix = getattr(request.state, "api_key_prefix", None)
        endpoint = request.url.path

        if user_id:
            _set_scope_user(scope, {"id": user_id})
            scope.set_tag("user_id", user_id)
        if api_key_prefix:
            scope.set_tag("api_key_prefix", api_key_prefix)
        scope.set_tag("endpoint", endpoint)
        scope.set_tag("request_id", getattr(request.state, "request_id", ""))
        scope.set_tag("backend", "supabase")
        scope.set_context(
            "request_context",
            {
                "method": request.method,
                "path": endpoint,
                "client": getattr(getattr(request, "client", None), "host", None),
            },
        )
        sentry_sdk.capture_exception(exc)
