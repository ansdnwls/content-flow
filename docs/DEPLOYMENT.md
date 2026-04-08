# ContentFlow — Deployment Guide

Step-by-step guide to deploy ContentFlow API on **Railway** with **Supabase** (PostgreSQL) and **Redis**.

## Architecture

```
                    ┌──────────────┐
                    │   Clients    │
                    └──────┬───────┘
                           │ HTTPS
                    ┌──────▼───────┐
                    │   Railway    │
                    │   (Proxy)    │
                    └──────┬───────┘
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼────┐ ┌─────▼─────┐
       │  API Server │ │Worker │ │   Beat    │
       │  (uvicorn)  │ │(celery│ │ (celery   │
       │  port 8000  │ │  x4)  │ │  beat)    │
       └──────┬──────┘ └──┬────┘ └─────┬─────┘
              │            │            │
       ┌──────▼────────────▼────────────▼─────┐
       │              Redis (broker)          │
       └──────────────────────────────────────┘
              │
       ┌──────▼──────────────────┐
       │   Supabase (PostgreSQL) │
       └─────────────────────────┘
```

## Prerequisites

- Railway account ([railway.app](https://railway.app))
- Supabase project ([supabase.com](https://supabase.com))
- Git repository with ContentFlow source code

## 1. Supabase Setup

### 1.1 Create Project

1. Create a new Supabase project at [app.supabase.com](https://app.supabase.com)
2. Note the **Project URL**, **anon key**, and **service_role key** from Settings > API

### 1.2 Run Migrations

Execute SQL files in order via the Supabase SQL Editor:

```bash
# 1. Schema (tables, indexes, triggers)
psql $SUPABASE_DB_URL -f infra/supabase/01_schema.sql

# 2. Row Level Security policies
psql $SUPABASE_DB_URL -f infra/supabase/02_rls.sql

# 3. Seed data (development only)
psql $SUPABASE_DB_URL -f infra/supabase/03_seed.sql
```

### 1.3 Verify Tables

Confirm these tables exist in Supabase Dashboard > Table Editor:

| Table | Description |
|-------|-------------|
| `users` | User accounts and plans |
| `api_keys` | Hashed API keys |
| `social_accounts` | Connected platform accounts |
| `posts` | Publishing jobs |
| `post_deliveries` | Per-platform delivery status |
| `video_jobs` | AI video generation queue |
| `webhooks` | Webhook subscriptions |
| `webhook_deliveries` | Delivery log + retry queue |
| `bombs` | Content bomb jobs |
| `comments` | Comment autopilot |
| `schedules` | Recurring post schedules |
| `analytics_snapshots` | Platform analytics |
| `video_templates` | Custom video templates |
| `trending_snapshots` | Trending topic snapshots |

## 2. Railway Setup

### 2.1 Create Project

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and initialize
railway login
railway init
```

### 2.2 Add Redis

1. In Railway dashboard, click **+ New** > **Database** > **Redis**
2. Railway auto-injects `REDIS_URL` into your services

### 2.3 Configure Services

Railway reads `infra/railway/railway.toml` for service configuration. Three services are defined:

| Service | Command | Replicas |
|---------|---------|----------|
| **api** | `uvicorn app.main:app` | 1+ |
| **worker** | `celery worker` | 1+ |
| **beat** | `celery beat` | 1 (exactly) |

### 2.4 Set Environment Variables

In Railway Dashboard > Service > Variables, set all variables from `.env.production.example`.

**Required variables:**

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Redis (auto-injected by Railway Redis plugin)
REDIS_URL=redis://...

# Security
TOKEN_ENCRYPTION_KEY=<32-byte-base64>
OAUTH_STATE_SECRET=<random-string>
```

Generate encryption keys:

```bash
# TOKEN_ENCRYPTION_KEY (Fernet-compatible, 32 bytes base64)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# OAUTH_STATE_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2.5 Deploy

```bash
# Run pre-deploy checks
./scripts/deploy_check.sh

# Deploy via Railway CLI
railway up

# Or push to linked Git branch for auto-deploy
git push origin main
```

## 3. OAuth Platform Setup

### 3.1 Google (YouTube + Google Business)

1. Go to [Google Cloud Console](https://console.cloud.google.com) > APIs & Services > Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Authorized redirect URI: `https://contentflow-api.railway.app/api/v1/accounts/callback/google`
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`

### 3.2 Meta (Instagram + Facebook + Threads)

1. Go to [Meta for Developers](https://developers.facebook.com) > Create App
2. Add Instagram Basic Display + Facebook Login products
3. Redirect URI: `https://contentflow-api.railway.app/api/v1/accounts/callback/meta`
4. Set `META_CLIENT_ID` and `META_CLIENT_SECRET`

### 3.3 TikTok

1. Go to [TikTok for Developers](https://developers.tiktok.com) > Manage Apps
2. Register app with Content Posting API scope
3. Redirect URI: `https://contentflow-api.railway.app/api/v1/accounts/callback/tiktok`
4. Set `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET`

### 3.4 X (Twitter)

1. Go to [X Developer Portal](https://developer.x.com) > Projects & Apps
2. Create app with OAuth 2.0 (User Authentication)
3. Redirect URI: `https://contentflow-api.railway.app/api/v1/accounts/callback/x`
4. Set `X_CLIENT_ID` and `X_CLIENT_SECRET`

## 4. Post-Deploy Verification

```bash
# 1. Health check
curl https://contentflow-api.railway.app/health

# 2. API docs
open https://contentflow-api.railway.app/docs

# 3. Check metrics (if Prometheus enabled)
curl https://contentflow-api.railway.app/metrics

# 4. Test API key authentication
curl -H "X-API-Key: cf_live_..." \
  https://contentflow-api.railway.app/api/v1/usage/summary
```

## 5. Scaling

### Horizontal Scaling

```toml
# Increase API replicas in railway.toml
[deploy.api]
numReplicas = 3

# Increase worker concurrency
[deploy.worker]
startCommand = "celery ... --concurrency=8"
```

### Beat Service

**Always keep exactly 1 replica** for the beat service to prevent duplicate scheduled tasks.

## 6. Monitoring

| Tool | Purpose | Config |
|------|---------|--------|
| Sentry | Error tracking | Set `SENTRY_DSN` |
| Prometheus | Metrics | `PROMETHEUS_ENABLED=true` (default) |
| Railway Logs | Application logs | Built-in via dashboard |
| `/health` | Liveness probe | Auto-configured |
| `/health/ready` | Readiness probe | Checks Redis + DB |

## Rollback

```bash
# Railway supports instant rollback via dashboard
# Or revert to previous deployment:
railway rollback
```
