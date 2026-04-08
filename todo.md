# ContentFlow TODO

## Completed
- [x] Project scaffolding (FastAPI + Supabase + Celery)
- [x] Supabase schema migration (7 tables + triggers + indexes)
- [x] Auth system (API key hashing with bcrypt, FastAPI dependency)
- [x] Posts CRUD API (create, get, list, cancel)
- [x] Global adapters x14: YouTube, TikTok, Instagram, X/Twitter, LinkedIn, Facebook, Threads, Pinterest, Reddit, Bluesky, Snapchat, Telegram, WordPress, Google Business
- [x] Asia adapters x4: Naver Blog, Tistory, Kakao, note.com (Japan)
- [x] Python SDK (sync + async clients)
- [x] JavaScript / TypeScript SDK
- [x] OAuth providers (Google, Meta, TikTok, X)
- [x] Celery workers (post_worker, video_worker, scheduler, comment, analytics)
- [x] Webhook dispatcher
- [x] Comment Autopilot (collect + AI reply + manual reply)
- [x] Viral score prediction + A/B variant generation
- [x] Schedule engine with recurring dispatch + recommendation windows
- [x] Billing-aware usage tracking + Redis-backed rate limiting
- [x] Analytics dashboard, comparison, ranking, and growth endpoints
- [x] OpenAPI export + docs metadata
- [x] Landing page + docs site (`landing/`)
- [x] CI/CD (GitHub Actions + Railway deploy)
- [x] Docker + docker-compose
- [x] 313 tests passing, ruff clean

## In Progress
- [ ] (none)

## Backlog

### API Enhancements
- [ ] Bulk posting endpoint (`POST /api/v1/posts/bulk`)
- [ ] Content transformation hardening (resize/crop rules per platform)
- [ ] API key rotation endpoint
- [ ] GDPR data export/deletion endpoints

### Platform Adapters
- [ ] LINE adapter (Japan/SEA messaging)
- [ ] WeChat / Weibo adapter (China market)
- [ ] Twitch adapter (live stream announcements)
- [ ] Mastodon adapter (ActivityPub/fediverse)
- [ ] Medium adapter (blog publishing)

### AI Video Generation
- [ ] Template system for video styles
- [ ] Provider abstraction beyond `yt-factory`
- [ ] Human review step before auto-publish

### SDK & Developer Experience
- [ ] Go SDK
- [ ] Webhook signature verification in SDKs
- [ ] SDK retry/backoff logic
- [ ] SDK examples and publish automation

### Infrastructure
- [ ] Production Supabase project (dedicated plan)
- [ ] Redis deployment for rate limiting + caching
- [ ] Monitoring & alerting (Sentry, Datadog)
- [ ] Logging & audit trail

### Security & Compliance
- [ ] OAuth token refresh automation
- [ ] Rate limit per-platform to respect API quotas
- [ ] Secret rotation runbook
