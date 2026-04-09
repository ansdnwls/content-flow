"""Startup configuration validator — checks env vars before the app serves."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("contentflow.config_validator")

_JWT_SECRET_DEFAULT = "change-me-in-production"


@dataclass(frozen=True)
class ValidationResult:
    """Immutable result of a configuration validation run."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Variable classification
# ---------------------------------------------------------------------------

REQUIRED_VARS: dict[str, str] = {
    "SUPABASE_URL": "Supabase project URL",
    "SUPABASE_SERVICE_ROLE_KEY": "Supabase service-role key",
    "REDIS_URL": "Redis connection URL",
    "JWT_SECRET": "JWT signing secret",
}

RECOMMENDED_VARS: dict[str, str] = {
    "TOKEN_ENCRYPTION_KEY": "AES key for OAuth token encryption",
    "OAUTH_STATE_SECRET": "Secret for OAuth CSRF state",
    "STRIPE_SECRET_KEY": "Stripe API secret key",
    "STRIPE_WEBHOOK_SECRET": "Stripe webhook signing secret",
    "RESEND_API_KEY": "Resend email API key",
    "SENTRY_DSN": "Sentry error tracking DSN",
    "ANTHROPIC_API_KEY": "Anthropic API key for AI features",
}

OPTIONAL_VARS: dict[str, str] = {
    "GOOGLE_CLIENT_ID": "Google OAuth client ID",
    "GOOGLE_CLIENT_SECRET": "Google OAuth client secret",
    "META_CLIENT_ID": "Meta OAuth app ID",
    "META_CLIENT_SECRET": "Meta OAuth app secret",
    "TIKTOK_CLIENT_KEY": "TikTok client key",
    "TIKTOK_CLIENT_SECRET": "TikTok client secret",
    "X_CLIENT_ID": "X (Twitter) OAuth client ID",
    "X_CLIENT_SECRET": "X (Twitter) OAuth client secret",
    "NAVER_COMMERCE_CLIENT_ID": "Naver Commerce client ID",
    "NAVER_COMMERCE_CLIENT_SECRET": "Naver Commerce client secret",
    "YT_FACTORY_BASE_URL": "yt-factory video generation URL",
    "YT_FACTORY_API_KEY": "yt-factory API key",
    "YOUTUBE_API_KEY": "YouTube Data API key",
}


def _get_env_value(settings: object, var_name: str) -> str | None:
    """Read a setting value by its env-var name (case-insensitive attr)."""
    attr = var_name.lower()
    val = getattr(settings, attr, None)
    if val is None or val == "":
        return None
    return str(val)


def validate_config(settings: object) -> ValidationResult:
    """Validate configuration and return errors/warnings.

    In development mode, rules are relaxed (missing recommended vars
    are not warned about, JWT default is allowed).
    """
    errors: list[str] = []
    warnings: list[str] = []

    app_env = _get_env_value(settings, "APP_ENV") or "development"
    is_prod = app_env.lower() in ("production", "staging")

    # --- Required vars ---
    for var, desc in REQUIRED_VARS.items():
        val = _get_env_value(settings, var)
        if var == "JWT_SECRET":
            if val == _JWT_SECRET_DEFAULT:
                if is_prod:
                    errors.append(
                        f"{var}: using default value '{_JWT_SECRET_DEFAULT}' "
                        "is not allowed in production"
                    )
            elif val is None and is_prod:
                errors.append(f"{var} is required ({desc})")
        elif val is None:
            errors.append(f"{var} is required ({desc})")

    # --- Recommended vars (warn only in production) ---
    if is_prod:
        for var, desc in RECOMMENDED_VARS.items():
            if _get_env_value(settings, var) is None:
                warnings.append(f"{var} is recommended ({desc})")

    # --- Production safety checks ---
    if is_prod:
        log_level = _get_env_value(settings, "LOG_LEVEL") or "INFO"
        if log_level.upper() == "DEBUG":
            warnings.append(
                "LOG_LEVEL=DEBUG in production exposes verbose output"
            )

    # --- CORS wildcard check (via OAUTH_REDIRECT_BASE_URL heuristic) ---
    redirect = _get_env_value(settings, "OAUTH_REDIRECT_BASE_URL") or ""
    if is_prod and redirect.startswith("http://localhost"):
        warnings.append(
            "OAUTH_REDIRECT_BASE_URL points to localhost in production"
        )

    return ValidationResult(errors=errors, warnings=warnings)


def validate_on_startup(settings: object) -> None:
    """Run validation and log results. Raises on fatal errors in production."""
    result = validate_config(settings)

    for w in result.warnings:
        logger.warning("Config warning: %s", w)

    if not result.ok:
        for e in result.errors:
            logger.error("Config error: %s", e)

        app_env = _get_env_value(settings, "APP_ENV") or "development"
        if app_env.lower() in ("production", "staging"):
            raise SystemExit(
                f"Startup blocked: {len(result.errors)} config error(s). "
                "Fix environment variables before deploying."
            )
        else:
            logger.warning(
                "Config has %d error(s) but APP_ENV=%s — continuing.",
                len(result.errors),
                app_env,
            )
    else:
        logger.info("Config validation passed (%d warnings)", len(result.warnings))
