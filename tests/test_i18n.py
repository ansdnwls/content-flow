"""Tests for backend i18n module."""

from __future__ import annotations

from app.core.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    email_subject,
    normalize_locale,
    t,
)


class TestNormalizeLocale:
    def test_supported_locale(self):
        assert normalize_locale("en") == "en"
        assert normalize_locale("ko") == "ko"
        assert normalize_locale("ja") == "ja"

    def test_locale_prefix(self):
        assert normalize_locale("en-US") == "en"
        assert normalize_locale("ko-KR") == "ko"
        assert normalize_locale("ja-JP") == "ja"

    def test_none_returns_default(self):
        assert normalize_locale(None) == DEFAULT_LOCALE

    def test_unsupported_returns_default(self):
        assert normalize_locale("fr") == DEFAULT_LOCALE
        assert normalize_locale("") == DEFAULT_LOCALE


class TestTranslation:
    def test_english_message(self):
        assert t("invalid_credentials", "en") == "Invalid email or password"

    def test_korean_message(self):
        msg = t("invalid_credentials", "ko")
        assert "이메일" in msg

    def test_japanese_message(self):
        msg = t("invalid_credentials", "ja")
        assert "メール" in msg

    def test_fallback_to_english_for_unknown_key(self):
        result = t("nonexistent_key", "ko")
        assert result == "nonexistent_key"

    def test_default_locale_used_when_none(self):
        result = t("unauthorized")
        assert result == t("unauthorized", DEFAULT_LOCALE)

    def test_all_locales_have_same_keys(self):
        from app.core.i18n import _MESSAGES

        en_keys = set(_MESSAGES["en"].keys())
        for locale in SUPPORTED_LOCALES:
            assert set(_MESSAGES[locale].keys()) == en_keys, (
                f"Locale '{locale}' has different keys than 'en'"
            )


class TestEmailSubject:
    def test_english_subject(self):
        assert email_subject("welcome", "en") == "Welcome to ContentFlow!"

    def test_korean_subject(self):
        subj = email_subject("welcome", "ko")
        assert "ContentFlow" in subj

    def test_japanese_subject(self):
        subj = email_subject("welcome", "ja")
        assert "ContentFlow" in subj

    def test_unknown_template_returns_name(self):
        assert email_subject("nonexistent", "en") == "nonexistent"


class TestEmailTemplateRendering:
    _welcome_vars = {
        "name": "Test",
        "dashboard_url": "#",
        "docs_url": "#",
        "unsubscribe_url": "#",
    }

    def test_render_localized_welcome(self):
        from app.services.email_service import render_template

        for locale in SUPPORTED_LOCALES:
            html = render_template(
                "welcome", self._welcome_vars, locale=locale,
            )
            assert "Test" in html
            assert "ContentFlow" in html

    def test_render_localized_verify_email(self):
        from app.services.email_service import render_template

        for locale in SUPPORTED_LOCALES:
            html = render_template(
                "verify_email",
                {"name": "User", "verify_url": "#"},
                locale=locale,
            )
            assert "User" in html

    def test_fallback_to_default_locale(self):
        from app.services.email_service import render_template

        # French doesn't exist, should fall back
        html = render_template(
            "welcome", self._welcome_vars, locale="fr",
        )
        assert "Test" in html
