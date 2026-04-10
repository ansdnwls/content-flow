from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="ContentFlow API", alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    structured_logging_enabled: bool = Field(
        default=True,
        alias="STRUCTURED_LOGGING_ENABLED",
    )
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_environment: str | None = Field(default=None, alias="SENTRY_ENVIRONMENT")
    sentry_traces_sample_rate: float = Field(default=0.0, alias="SENTRY_TRACES_SAMPLE_RATE")
    sentry_profiles_sample_rate: float = Field(
        default=0.0,
        alias="SENTRY_PROFILES_SAMPLE_RATE",
    )
    prometheus_enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")

    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_anon_key: str | None = Field(default=None, alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_db_url: str | None = Field(default=None, alias="SUPABASE_DB_URL")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str | None = Field(default=None, alias="CELERY_BROKER_URL")
    celery_result_backend: str | None = Field(default=None, alias="CELERY_RESULT_BACKEND")

    api_key_prefix: str = Field(default="cf_live", alias="API_KEY_PREFIX")
    api_key_bytes: int = Field(default=24, alias="API_KEY_BYTES")
    api_key_cache_ttl_seconds: int = Field(default=300, alias="API_KEY_CACHE_TTL_SECONDS")
    api_key_last_used_update_seconds: int = Field(
        default=60,
        alias="API_KEY_LAST_USED_UPDATE_SECONDS",
    )

    # OAuth / Token encryption
    token_encryption_key: str | None = Field(default=None, alias="TOKEN_ENCRYPTION_KEY")
    oauth_state_secret: str | None = Field(default=None, alias="OAUTH_STATE_SECRET")
    oauth_redirect_base_url: str = Field(
        default="http://localhost:8000", alias="OAUTH_REDIRECT_BASE_URL"
    )
    token_refresh_leeway_seconds: int = Field(
        default=300,
        alias="TOKEN_REFRESH_LEEWAY_SECONDS",
    )

    # yt-factory
    yt_factory_base_url: str | None = Field(default=None, alias="YT_FACTORY_BASE_URL")
    yt_factory_api_key: str | None = Field(default=None, alias="YT_FACTORY_API_KEY")
    yt_factory_timeout_seconds: int = Field(default=900, alias="YT_FACTORY_TIMEOUT_SECONDS")
    yt_factory_poll_interval_seconds: float = Field(
        default=5.0,
        alias="YT_FACTORY_POLL_INTERVAL_SECONDS",
    )

    # Google (YouTube + Google Business)
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")

    # Meta (Instagram + Facebook + Threads)
    meta_client_id: str | None = Field(default=None, alias="META_CLIENT_ID")
    meta_client_secret: str | None = Field(default=None, alias="META_CLIENT_SECRET")

    # TikTok
    tiktok_client_key: str | None = Field(default=None, alias="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str | None = Field(default=None, alias="TIKTOK_CLIENT_SECRET")

    # X (Twitter)
    x_client_id: str | None = Field(default=None, alias="X_CLIENT_ID")
    x_client_secret: str | None = Field(default=None, alias="X_CLIENT_SECRET")

    # Naver Commerce (SmartStore)
    naver_commerce_client_id: str | None = Field(
        default=None,
        alias="NAVER_COMMERCE_CLIENT_ID",
    )
    naver_commerce_client_secret: str | None = Field(
        default=None,
        alias="NAVER_COMMERCE_CLIENT_SECRET",
    )
    naver_commerce_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/accounts/callback/naver_commerce",
        alias="NAVER_COMMERCE_REDIRECT_URI",
    )

    # Coupang WING
    coupang_access_key: str | None = Field(
        default=None, alias="COUPANG_ACCESS_KEY",
    )
    coupang_secret_key: str | None = Field(
        default=None, alias="COUPANG_SECRET_KEY",
    )
    coupang_vendor_id: str | None = Field(
        default=None, alias="COUPANG_VENDOR_ID",
    )

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    comment_poll_interval_seconds: int = Field(
        default=300, alias="COMMENT_POLL_INTERVAL_SECONDS"
    )
    anthropic_model: str = Field(default="claude-3-5-sonnet-latest", alias="ANTHROPIC_MODEL")
    anthropic_api_base_url: str = Field(
        default="https://api.anthropic.com/v1",
        alias="ANTHROPIC_API_BASE_URL",
    )

    # YouTube Data API (for trending)
    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")
    ytboost_base_url: str = Field(
        default="http://localhost:8000",
        alias="YTBOOST_BASE_URL",
    )
    ytboost_webhook_secret: str | None = Field(
        default=None,
        alias="YTBOOST_WEBHOOK_SECRET",
    )

    # Stripe billing
    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_build_monthly: str = Field(
        default="price_build_monthly", alias="STRIPE_PRICE_BUILD_MONTHLY",
    )
    stripe_price_build_yearly: str = Field(
        default="price_build_yearly", alias="STRIPE_PRICE_BUILD_YEARLY",
    )
    stripe_price_scale_monthly: str = Field(
        default="price_scale_monthly", alias="STRIPE_PRICE_SCALE_MONTHLY",
    )
    stripe_price_scale_yearly: str = Field(
        default="price_scale_yearly", alias="STRIPE_PRICE_SCALE_YEARLY",
    )
    stripe_price_enterprise_monthly: str = Field(
        default="price_enterprise_monthly", alias="STRIPE_PRICE_ENTERPRISE_MONTHLY",
    )
    stripe_price_enterprise_yearly: str = Field(
        default="price_enterprise_yearly", alias="STRIPE_PRICE_ENTERPRISE_YEARLY",
    )
    stripe_success_url: str = Field(
        default="https://contentflow.dev/billing/success", alias="STRIPE_SUCCESS_URL",
    )
    stripe_cancel_url: str = Field(
        default="https://contentflow.dev/billing/cancel", alias="STRIPE_CANCEL_URL",
    )

    # Email (Resend)
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")
    email_from: str = Field(
        default="noreply@contentflow.dev", alias="EMAIL_FROM",
    )
    email_from_name: str = Field(
        default="ContentFlow", alias="EMAIL_FROM_NAME",
    )
    email_reply_to: str = Field(
        default="support@contentflow.dev", alias="EMAIL_REPLY_TO",
    )
    email_dashboard_url: str = Field(
        default="https://contentflow.dev/dashboard",
        alias="EMAIL_DASHBOARD_URL",
    )
    email_docs_url: str = Field(
        default="https://contentflow.dev/docs", alias="EMAIL_DOCS_URL",
    )
    email_unsubscribe_base: str = Field(
        default="https://contentflow.dev/unsubscribe",
        alias="EMAIL_UNSUBSCRIBE_BASE",
    )
    jwt_secret: str = Field(
        default="change-me-in-production", alias="JWT_SECRET",
    )

    railway_environment: str = Field(default="production", alias="RAILWAY_ENVIRONMENT")

    @property
    def effective_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.effective_celery_broker_url

    @property
    def supabase_service_key(self) -> str | None:
        return self.supabase_service_role_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
