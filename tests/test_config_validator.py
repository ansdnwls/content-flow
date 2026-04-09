"""Tests for startup configuration validator."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config_validator import (
    ValidationResult,
    validate_config,
    validate_on_startup,
)


def _settings(**overrides: object) -> SimpleNamespace:
    """Build a minimal settings object with sane defaults."""
    defaults = {
        "app_env": "development",
        "supabase_url": "https://test.supabase.co",
        "supabase_service_role_key": "test-key",
        "redis_url": "redis://localhost:6379/0",
        "jwt_secret": "real-secret-here",
        "token_encryption_key": "enc-key",
        "oauth_state_secret": "state-secret",
        "stripe_secret_key": "sk_test_xxx",
        "stripe_webhook_secret": "whsec_xxx",
        "resend_api_key": "re_xxx",
        "sentry_dsn": "https://sentry.io/xxx",
        "anthropic_api_key": "sk-ant-xxx",
        "log_level": "INFO",
        "oauth_redirect_base_url": "https://contentflow-api.railway.app",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# 1. All required vars present → no errors
def test_valid_config_no_errors():
    result = validate_config(_settings())
    assert result.ok
    assert result.errors == []


# 2. Missing SUPABASE_URL → error
def test_missing_supabase_url():
    result = validate_config(_settings(supabase_url=""))
    assert not result.ok
    assert any("SUPABASE_URL" in e for e in result.errors)


# 3. Missing REDIS_URL → error
def test_missing_redis_url():
    result = validate_config(_settings(redis_url=None))
    assert not result.ok
    assert any("REDIS_URL" in e for e in result.errors)


# 4. JWT_SECRET default in production → error
def test_jwt_default_in_production():
    result = validate_config(
        _settings(app_env="production", jwt_secret="change-me-in-production"),
    )
    assert not result.ok
    assert any("JWT_SECRET" in e and "default" in e for e in result.errors)


# 5. JWT_SECRET default in development → allowed (no error)
def test_jwt_default_in_dev_allowed():
    result = validate_config(
        _settings(app_env="development", jwt_secret="change-me-in-production"),
    )
    assert result.ok


# 6. Missing recommended var in production → warning
def test_missing_recommended_in_prod():
    result = validate_config(
        _settings(app_env="production", stripe_secret_key=""),
    )
    assert any("STRIPE_SECRET_KEY" in w for w in result.warnings)


# 7. Missing recommended var in development → no warning
def test_missing_recommended_in_dev_no_warning():
    result = validate_config(
        _settings(app_env="development", stripe_secret_key=""),
    )
    assert not any("STRIPE_SECRET_KEY" in w for w in result.warnings)


# 8. LOG_LEVEL=DEBUG in production → warning
def test_debug_log_in_production():
    result = validate_config(
        _settings(app_env="production", log_level="DEBUG"),
    )
    assert any("LOG_LEVEL" in w and "DEBUG" in w for w in result.warnings)


# 9. localhost redirect in production → warning
def test_localhost_redirect_in_production():
    result = validate_config(
        _settings(
            app_env="production",
            oauth_redirect_base_url="http://localhost:8000",
        ),
    )
    assert any("localhost" in w for w in result.warnings)


# 10. validate_on_startup raises SystemExit in production with errors
def test_validate_on_startup_raises_in_production():
    bad_settings = _settings(app_env="production", supabase_url="")
    with pytest.raises(SystemExit):
        validate_on_startup(bad_settings)


# 11. validate_on_startup does NOT raise in development with errors
def test_validate_on_startup_continues_in_dev():
    bad_settings = _settings(app_env="development", supabase_url="")
    # Should not raise — just logs warnings
    validate_on_startup(bad_settings)


# 12. ValidationResult.ok property
def test_validation_result_ok():
    ok_result = ValidationResult(errors=[], warnings=["minor"])
    assert ok_result.ok

    bad_result = ValidationResult(errors=["fatal"], warnings=[])
    assert not bad_result.ok
