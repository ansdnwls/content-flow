"""Optional Sentry initialization helpers."""

from __future__ import annotations

from fastapi import Request

from app.config import Settings, get_settings

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - optional dependency
    sentry_sdk = None

try:  # pragma: no cover - optional dependency
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except Exception:  # pragma: no cover - optional dependency
    FastApiIntegration = None


def init_sentry(settings: Settings | None = None) -> bool:
    """Initialize Sentry when a DSN is configured and the SDK is installed."""
    settings = settings or get_settings()
    if not settings.sentry_dsn or sentry_sdk is None:
        return False

    integrations = [FastApiIntegration()] if FastApiIntegration is not None else []
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=integrations,
    )
    return True


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
            scope.user = {"id": user_id}
            scope.set_tag("user_id", user_id)
        if api_key_prefix:
            scope.set_tag("api_key_prefix", api_key_prefix)
        scope.set_tag("endpoint", endpoint)
        scope.set_tag("request_id", getattr(request.state, "request_id", ""))
        sentry_sdk.capture_exception(exc)
