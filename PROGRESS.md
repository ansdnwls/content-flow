# Progress

Current project status lives in [`CHANGELOG.md`](./CHANGELOG.md).

## Current Status

- Version target: `0.2.0`
- Date: `2026-04-08`
- Vertical Launcher system completed (template + 2 verticals)
- YtBoost backend v1 completed (trigger, shorts, distributor, comment autopilot)
- ShopSync backend v1 completed (Product Content Bomb engine)
- Validation completed:
  - API quality: `ruff check .` — clean
  - API tests: `pytest -q` — **707 passed**

## Completed

- **Vertical Launcher** — Template system for rapid vertical product creation
  - `packages/cf-config/` — TypeScript types + JSON schema
  - `packages/cf-ui/` — 7 shared components + 4 widgets
  - `packages/cf-engine/` — ContentFlow API client wrapper
  - `verticals/_template/` — Full template (landing + dashboard + presets)
  - `tools/create-vertical/` — Interactive CLI for vertical scaffolding
  - `.github/workflows/deploy-vertical.yml` — Change-detection deployment
- **YtBoost vertical** (`verticals/ytboost/`) — YouTube creator amplifier
  - Config, landing, dashboard, presets, vercel.json
  - Backend: YouTube trigger, shorts extractor, distributor, comment autopilot
  - API: 12 endpoints, PubSubHubbub + yt-factory webhooks
  - DB: 4 tables (subscriptions, shorts, channel_tones, detected_videos)
  - Tests: 13 passed
- **ShopSync vertical** (`verticals/shopsync/`) — Ecommerce seller autopilot
  - Config, landing, dashboard, presets, vercel.json
  - Backend: Product Content Bomb, 5 channel renderers, adapters, OAuth
  - Tests: 20 passed
- GDPR backend core completed
- GDPR frontend/legal surface completed
- Mintlify-based public API docs site completed
- Auth cache, response cache, performance indexes, and batch audit writer added
- Comment Autopilot completed
- Viral Score prediction and A/B variants completed
- Scheduling Engine completed
- Rate limiting and Usage Dashboard completed
- OpenAPI export and documentation completed
- Analytics Engine completed
- Webhook Retry Queue + Dead Letter Queue completed
- OAuth token refresh automation and platform rate limiting completed
- Monitoring, health checks, and Prometheus-ready metrics completed
- i18n (ko/en/ja) for dashboard, landing, email templates, backend completed

## Remaining

- Deploy `docs-site/` to Mintlify Cloud or Vercel preview flow and attach `docs.contentflow.dev`
- Replace placeholder docs screenshots with product screenshots if desired
- Clean up non-blocking build warnings in `landing`:
  - Turbopack workspace root warning
  - `middleware` to `proxy` migration warning
- Continue next queued feature/task in a new session only

## Notes

- Use `CHANGELOG.md` for release notes and shipped milestones.
- Use this file only as a lightweight handoff pointer.
