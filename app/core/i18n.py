"""Backend i18n support — localized error messages and email subjects."""

from __future__ import annotations

SUPPORTED_LOCALES = ("en", "ko", "ja")
DEFAULT_LOCALE = "ko"

# ---------------------------------------------------------------------------
# Translated error / status messages keyed by (locale, message_key)
# ---------------------------------------------------------------------------
_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Auth
        "invalid_credentials": "Invalid email or password",
        "missing_api_key": "Missing X-API-Key header",
        "invalid_api_key": "Invalid API key",
        "unauthorized": "Authentication required",
        "forbidden": "Access denied",
        # Billing
        "billing_limit_exceeded": "Post limit exceeded for your plan",
        "plan_required": "Upgrade your plan to use this feature",
        # Posts
        "post_not_found": "Post not found",
        "post_create_failed": "Failed to create post",
        # Videos
        "video_not_found": "Video not found",
        "video_create_failed": "Failed to generate video",
        # Validation
        "required_field": "This field is required",
        "invalid_email": "Invalid email format",
        "password_too_short": "Password must be at least 8 characters",
        # Rate limit
        "rate_limit": "Too many requests. Please try again later.",
        # General
        "not_found": "Not found",
        "internal_error": "An internal error occurred",
        "network_error": "A network error occurred",
    },
    "ko": {
        "invalid_credentials": "이메일 또는 비밀번호가 올바르지 않습니다",
        "missing_api_key": "X-API-Key 헤더가 없습니다",
        "invalid_api_key": "유효하지 않은 API 키입니다",
        "unauthorized": "인증이 필요합니다",
        "forbidden": "접근 권한이 없습니다",
        "billing_limit_exceeded": "플랜의 포스트 한도를 초과했습니다",
        "plan_required": "이 기능을 사용하려면 플랜을 업그레이드하세요",
        "post_not_found": "포스트를 찾을 수 없습니다",
        "post_create_failed": "포스트 생성에 실패했습니다",
        "video_not_found": "영상을 찾을 수 없습니다",
        "video_create_failed": "영상 생성에 실패했습니다",
        "required_field": "필수 항목입니다",
        "invalid_email": "올바른 이메일 형식이 아닙니다",
        "password_too_short": "비밀번호는 8자 이상이어야 합니다",
        "rate_limit": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
        "not_found": "찾을 수 없습니다",
        "internal_error": "내부 오류가 발생했습니다",
        "network_error": "네트워크 오류가 발생했습니다",
    },
    "ja": {
        "invalid_credentials": "メールアドレスまたはパスワードが無効です",
        "missing_api_key": "X-API-Keyヘッダーがありません",
        "invalid_api_key": "無効なAPIキーです",
        "unauthorized": "認証が必要です",
        "forbidden": "アクセスが拒否されました",
        "billing_limit_exceeded": "プランの投稿上限を超えました",
        "plan_required": "この機能を利用するにはプランのアップグレードが必要です",
        "post_not_found": "投稿が見つかりません",
        "post_create_failed": "投稿の作成に失敗しました",
        "video_not_found": "動画が見つかりません",
        "video_create_failed": "動画の生成に失敗しました",
        "required_field": "必須項目です",
        "invalid_email": "無効なメール形式です",
        "password_too_short": "パスワードは8文字以上必要です",
        "rate_limit": "リクエストが多すぎます。しばらくしてから再試行してください。",
        "not_found": "見つかりません",
        "internal_error": "内部エラーが発生しました",
        "network_error": "ネットワークエラーが発生しました",
    },
}

# Email subjects per locale
EMAIL_SUBJECTS: dict[str, dict[str, str]] = {
    "en": {
        "welcome": "Welcome to ContentFlow!",
        "verify_email": "Verify your email address",
        "password_reset": "Reset your password",
        "billing_invoice": "Your ContentFlow invoice",
        "billing_upgraded": "Your plan has been upgraded",
        "security_alert": "Security alert for your account",
    },
    "ko": {
        "welcome": "ContentFlow에 오신 것을 환영합니다!",
        "verify_email": "이메일 주소를 인증해주세요",
        "password_reset": "비밀번호를 재설정하세요",
        "billing_invoice": "ContentFlow 인보이스",
        "billing_upgraded": "플랜이 업그레이드되었습니다",
        "security_alert": "계정 보안 알림",
    },
    "ja": {
        "welcome": "ContentFlowへようこそ！",
        "verify_email": "メールアドレスを確認してください",
        "password_reset": "パスワードをリセットしてください",
        "billing_invoice": "ContentFlowの請求書",
        "billing_upgraded": "プランがアップグレードされました",
        "security_alert": "アカウントのセキュリティアラート",
    },
}


def normalize_locale(locale: str | None) -> str:
    """Return a supported locale, falling back to DEFAULT_LOCALE."""
    if locale and locale[:2] in SUPPORTED_LOCALES:
        return locale[:2]
    return DEFAULT_LOCALE


def t(key: str, locale: str | None = None) -> str:
    """Look up a translated message by key and locale."""
    loc = normalize_locale(locale)
    return _MESSAGES.get(loc, _MESSAGES[DEFAULT_LOCALE]).get(
        key,
        _MESSAGES["en"].get(key, key),
    )


def email_subject(template_name: str, locale: str | None = None) -> str:
    """Look up a translated email subject."""
    loc = normalize_locale(locale)
    return EMAIL_SUBJECTS.get(loc, EMAIL_SUBJECTS[DEFAULT_LOCALE]).get(
        template_name,
        EMAIL_SUBJECTS["en"].get(template_name, template_name),
    )
