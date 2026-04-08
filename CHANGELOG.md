# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-04-07

### Added

- Webhook retry queue with exponential backoff, dead letter queue handling, signed delivery verification helpers, and replay APIs.
- Automatic OAuth token refresh worker with account expiration handling and `account.disconnected` webhook dispatch.
- Platform-aware publish limiter for YouTube, TikTok, Instagram, X, and LinkedIn with delayed scheduling for the next available slot.
- Monitoring stack with structured JSON logging, request IDs, Sentry hooks, Prometheus-format metrics, and expanded health endpoints.
- Additional adapters and tests for LINE, Mastodon, and Medium publishing flows.
- Parallel GitHub Actions workflows for CI, tagged releases, SDK publishing, GHCR image publishing, and Railway deployment health checks.
- `Makefile` shortcuts for linting, testing, builds, Docker lifecycle, SDK packaging, and release tagging.

### Changed

- Bumped API and SDK release metadata to `0.2.0` for synchronized publishing across Python, JavaScript, Go, and landing artifacts.
- Expanded operational visibility with readiness probes for Supabase, Redis, and Celery plus runtime queue and worker metrics.
- Automated Go SDK release tagging so repository release tags also generate the module tag consumed by `pkg.go.dev`.

### Verification

- API quality: `ruff check .`
- API tests: `pytest -q`
- CI coverage target: `pytest --cov=app --cov-fail-under=80`
- SDK and landing validation wired into parallel GitHub Actions jobs

## [0.1.0] - 2026-04-07

### Added

- FastAPI API surface for posts, videos, bombs, comments, predict, schedules, usage, accounts, and analytics.
- Support for 18 publishing platforms including regional channels such as Naver Blog, Tistory, Kakao, and note.com.
- OAuth provider integrations for Google, Meta, TikTok, and X.
- AES-256 encrypted token storage with refresh support for connected social accounts.
- `yt-factory` backed video generation worker with auto-publish flow into the Posts API.
- Content Bomb transformation pipeline for generating platform-specific variants from one topic.
- Comment Autopilot with collection, AI reply generation, manual reply endpoint, and Celery scheduling.
- Viral Score prediction endpoints with heuristic scoring and A/B test variant generation.
- Schedule engine with timezone-aware recurring publish windows and recommendation endpoints.
- Analytics Engine with dashboard aggregation, platform comparison, top-posts ranking, and follower growth tracking.
- Analytics snapshot worker for daily data collection from YouTube, TikTok, and Instagram adapters.
- Usage tracking, billing-plan quotas, and Redis-backed request rate limiting headers.
- Python SDK in `sdk/python` and JavaScript SDK in `sdk/javascript`.
- Production landing page and API docs site in `landing/`, deployed to Vercel.
- Docker Compose stack for local `api`, `worker`, `beat`, and `redis`.
- OpenAPI metadata improvements, shared error response models, and export tooling.

### Changed

- Reworked local developer onboarding with Docker-first startup and a dedicated landing site workflow.
- Updated API documentation coverage to include comments, bombs, predict, schedules, and usage routes.
- Promoted the progress log into release-note format under `CHANGELOG.md`.

### Fixed

- Completed remaining `ruff` line-length cleanup for Content Bomb code paths.
- Wired video generation completion into internal post creation and publish dispatch.
- Connected encrypted OAuth token loading to real publish flows.
- Corrected usage history aggregation to preserve test coverage for billing and dashboards.

### Verification

- `landing`: `npm run build`
- API: `docker compose up --build -d`
- Swagger: `http://localhost:8000/docs` returned `200`
- Quality: `ruff check .`
- Tests: `pytest -q`
