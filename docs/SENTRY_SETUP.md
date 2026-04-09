# Sentry Setup

## Overview

ContentFlow initializes Sentry only when `SENTRY_DSN` is configured. The backend sets:

- `release` from `git rev-parse --short HEAD`
- `environment` from `SENTRY_ENVIRONMENT` or `APP_ENV`
- `before_send` redaction for email, phone numbers, bearer tokens, JWTs, API keys, cookies, and secrets
- FastAPI, Celery, Redis, and optional SQLAlchemy integrations when the SDK packages are available

Supabase-backed requests are tagged with `backend=supabase` so production issues can be filtered separately from other runtime errors.

## 1. Create A Sentry Project

1. Sign in to Sentry and create a new organization or select an existing one.
2. Create a project for the backend API using the Python platform.
3. Copy the DSN from the project settings page.

## 2. Configure Environment Variables

Add these variables to production secrets:

```env
SENTRY_DSN=https://xxx@sentry.io/yyy
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.0
```

Recommended starting values:

- `SENTRY_TRACES_SAMPLE_RATE=0.05` to `0.1`
- `SENTRY_PROFILES_SAMPLE_RATE=0.0` initially, then raise gradually after validating cost and signal quality

## 3. Backend Integration Points

The API process initializes Sentry during application startup through [monitoring.py](/C:/Users/y2k_w/projects/content-flow/app/core/monitoring.py).

The Celery worker initializes Sentry during worker bootstrap through [celery_app.py](/C:/Users/y2k_w/projects/content-flow/app/workers/celery_app.py).

This captures:

- FastAPI request exceptions
- Celery task failures
- Redis breadcrumbs and failures when the SDK integration is installed
- SQLAlchemy errors if SQLAlchemy is added later and the integration module is available

## 4. Alerts

Create at least these alerts in Sentry:

1. `level:error` or higher in `production`
2. New issue in `production`
3. Spike in transaction failure rate
4. Spike in p95 transaction latency

Suggested routing:

- Error alerts to engineering chat
- Regression alerts to the on-call rotation
- Release health alerts to the deployment channel

## 5. Release Tracking

Backend releases are tagged automatically from the current git commit hash. In CI/CD, ensure deployments are built from clean commits so the release value matches the running revision.

If you use Sentry CLI in deployment automation, create and finalize the same release name before rollout:

```bash
export RELEASE=$(git rev-parse --short HEAD)
sentry-cli releases new "$RELEASE"
sentry-cli releases finalize "$RELEASE"
```

## 6. Frontend Source Maps

If a frontend app is deployed separately, upload source maps from the frontend build pipeline using the same release value:

```bash
export RELEASE=$(git rev-parse --short HEAD)
sentry-cli releases files "$RELEASE" upload-sourcemaps ./dist --rewrite
```

Use the same `SENTRY_ENVIRONMENT` value in the frontend so cross-service issue grouping stays consistent.

## 7. Validation Checklist

1. Deploy with `SENTRY_DSN` enabled in staging first.
2. Trigger a handled test error from the API.
3. Confirm the event shows the correct `release`, `environment`, and `backend=supabase` tag.
4. Verify emails, phones, and tokens are masked in the final event payload.
5. Confirm noisy `401`, `404`, and `429` errors are suppressed.
