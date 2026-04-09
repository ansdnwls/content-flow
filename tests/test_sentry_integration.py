from __future__ import annotations

from app.config import Settings
from app.core.errors import AuthenticationError


def test_init_sentry_is_noop_without_dsn(monkeypatch) -> None:
    import app.core.sentry_init as sentry_init

    monkeypatch.setattr(
        sentry_init,
        "get_settings",
        lambda: Settings(APP_ENV="production", SENTRY_DSN=None),
    )
    monkeypatch.setattr(sentry_init, "sentry_sdk", object())

    assert sentry_init.init_sentry() is False


def test_mask_pii_redacts_email_phone_and_tokens() -> None:
    from app.core.sentry_init import mask_pii

    masked = mask_pii(
        {
            "email": "person@example.com",
            "phone": "+82 10-1234-5678",
            "access_token": "Bearer secret-token-value",
            "note": "reach me at person@example.com or +82 10-1234-5678",
        }
    )

    assert masked["email"] == "[masked-email]"
    assert masked["phone"] == "[masked-phone]"
    assert masked["access_token"] == "[masked-token]"
    assert "[masked-email]" in masked["note"]
    assert "[masked-phone]" in masked["note"]


def test_init_sentry_injects_release_and_environment(monkeypatch) -> None:
    import app.core.sentry_init as sentry_init

    captured: dict = {}

    class FakeSentry:
        def init(self, **kwargs):
            captured.update(kwargs)

        def set_tag(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(
        sentry_init,
        "_get_release_tag",
        lambda: "abc1234",
    )
    monkeypatch.setattr(
        sentry_init,
        "get_settings",
        lambda: Settings(
            APP_ENV="development",
            SENTRY_DSN="https://example@sentry.io/1",
            SENTRY_ENVIRONMENT="production",
            SENTRY_TRACES_SAMPLE_RATE=0.25,
            SENTRY_PROFILES_SAMPLE_RATE=0.1,
        ),
    )
    monkeypatch.setattr(sentry_init, "sentry_sdk", FakeSentry())
    monkeypatch.setattr(sentry_init, "FastApiIntegration", lambda: "fastapi")
    monkeypatch.setattr(sentry_init, "CeleryIntegration", None)
    monkeypatch.setattr(sentry_init, "RedisIntegration", None)
    monkeypatch.setattr(sentry_init, "SqlalchemyIntegration", None)

    assert sentry_init.init_sentry() is True
    assert captured["release"] == "abc1234"
    assert captured["environment"] == "production"
    assert captured["traces_sample_rate"] == 0.25
    assert captured["profiles_sample_rate"] == 0.1


def test_before_send_masks_payload(monkeypatch) -> None:
    import app.core.sentry_init as sentry_init

    event = {
        "user": {"id": "user-1", "email": "person@example.com"},
        "request": {
            "headers": {
                "authorization": "Bearer secret-token",
            }
        },
        "extra": {
            "phone": "+1 (555) 123-4567",
        },
    }

    masked = sentry_init.before_send(event, {})

    assert masked is not None
    assert masked["user"]["email"] == "[masked-email]"
    assert masked["request"]["headers"]["authorization"] == "[masked-token]"
    assert masked["extra"]["phone"] == "[masked-phone]"


def test_before_send_ignores_expected_noise() -> None:
    import app.core.sentry_init as sentry_init

    ignored = sentry_init.before_send(
        {"message": "missing auth"},
        {"exc_info": (AuthenticationError, AuthenticationError(), None)},
    )

    assert ignored is None


def test_set_user_context_sets_sdk_user(monkeypatch) -> None:
    import app.core.sentry_init as sentry_init

    captured: dict = {}

    class FakeSentry:
        def set_user(self, payload):
            captured["user"] = payload

    monkeypatch.setattr(
        sentry_init,
        "get_settings",
        lambda: Settings(APP_ENV="production", SENTRY_DSN="https://example@sentry.io/1"),
    )
    monkeypatch.setattr(sentry_init, "sentry_sdk", FakeSentry())

    sentry_init.set_user_context("user-123", "person@example.com")

    assert captured["user"] == {"id": "user-123", "email": "person@example.com"}
