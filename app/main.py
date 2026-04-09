from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.health import router as health_router
from app.api.router import api_router
from app.api.webhooks.stripe import router as stripe_webhook_router
from app.api.webhooks.youtube import router as youtube_webhook_router
from app.api.webhooks.yt_factory import router as yt_factory_webhook_router
from app.config import get_settings
from app.core.audit import reset_audit_writer
from app.core.cache import reset_redis_client as reset_cache_redis_client
from app.core.middleware import ErrorTrackingMiddleware, LoggingMiddleware
from app.core.monitoring import setup_monitoring
from app.core.request_id import RequestIdMiddleware
from app.core.request_validator import RequestValidatorMiddleware
from app.core.response_cache import ResponseCacheInvalidationMiddleware
from app.core.security_middleware import SecurityHeadersMiddleware
from app.core.timing_middleware import TimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await reset_audit_writer()
    await app.state.redis.aclose()
    reset_cache_redis_client()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    summary="Multi-platform social publishing and AI video generation API.",
    description=(
        "ContentFlow exposes a unified API for multi-platform publishing, "
        "scheduled delivery, video generation, AI comment replies, "
        "content bomb distribution, and viral score prediction.\n\n"
        "## Authentication\n"
        "All endpoints require an `X-API-Key` header. "
        "Keys are prefixed with `cf_live_` (production) or `cf_test_` (sandbox).\n\n"
        "## Rate Limiting\n"
        "Requests are rate-limited per plan. "
        "See `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and "
        "`X-RateLimit-Reset` response headers."
    ),
    version="0.2.0",
    lifespan=lifespan,
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
        {
            "url": "https://contentflow-api.railway.app",
            "description": "Production (Railway)",
        },
    ],
    contact={"name": "ContentFlow API", "url": "https://contentflow.dev"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {
            "name": "Posts",
            "description": "Create, schedule, inspect, and cancel multi-platform publishing jobs.",
        },
        {
            "name": "Videos",
            "description": "Queue AI video generation workflows and inspect job status.",
        },
        {
            "name": "Bombs",
            "description": (
                "Content Bomb - expand a single topic into platform-specific variants "
                "and publish them in bulk."
            ),
        },
        {
            "name": "Comments",
            "description": (
                "Comment Autopilot - collect comments from platform posts and "
                "generate AI-powered replies."
            ),
        },
        {
            "name": "Prediction",
            "description": (
                "Viral score prediction and A/B test variant generation "
                "powered by AI analysis."
            ),
        },
        {
            "name": "Schedules",
            "description": (
                "Recurring post schedules with timezone support and "
                "optimal time recommendations."
            ),
        },
        {
            "name": "Usage",
            "description": (
                "Usage dashboard - monthly summary, daily history, "
                "and plan-based billing limits."
            ),
        },
        {
            "name": "Webhooks",
            "description": (
                "Webhook management - delivery history, manual redelivery, "
                "and dead letter queue for failed deliveries."
            ),
        },
        {
            "name": "Accounts",
            "description": (
                "OAuth account connections - connect, list, and disconnect "
                "social media accounts."
            ),
        },
        {
            "name": "Analytics",
            "description": "Read owner-level publishing and generation summaries.",
        },
        {
            "name": "Trending",
            "description": (
                "Real-time trend discovery across YouTube, Reddit, and Google Trends "
                "with scored topic recommendations and content generation."
            ),
        },
        {
            "name": "Admin",
            "description": (
                "Admin panel — user management, plan changes, "
                "system statistics, and health monitoring."
            ),
        },
        {
            "name": "YtBoost",
            "description": (
                "YouTube-first growth workflows including channel subscriptions, "
                "shorts extraction, distribution, and reply approval."
            ),
        },
        {
            "name": "ops",
            "description": "Operational health, metrics, and runtime checks.",
        },
    ],
)

setup_monitoring(app)


def configure_http_middleware(fastapi_app: FastAPI) -> None:
    """Install middleware in reverse registration order of the desired request flow.

    FastAPI wraps the most recently added middleware on the outside. The intended
    execution flow is RequestID -> Timing -> Auth -> RateLimit -> Cache -> Logging.
    Auth and rate limiting run inside route dependencies after outer middleware.
    """

    fastapi_app.add_middleware(SecurityHeadersMiddleware)
    fastapi_app.add_middleware(RequestValidatorMiddleware)
    fastapi_app.add_middleware(ErrorTrackingMiddleware)
    fastapi_app.add_middleware(LoggingMiddleware)
    fastapi_app.add_middleware(ResponseCacheInvalidationMiddleware)
    fastapi_app.add_middleware(TimingMiddleware)
    fastapi_app.add_middleware(RequestIdMiddleware)


configure_http_middleware(app)

app.include_router(api_router)
app.include_router(stripe_webhook_router)
app.include_router(youtube_webhook_router)
app.include_router(yt_factory_webhook_router)
app.include_router(health_router)
