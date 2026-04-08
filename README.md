# ContentFlow

AI-native social publishing infrastructure for creating, scheduling, predicting, and distributing content across 18 platforms from one API.

## Overview

ContentFlow combines a FastAPI backend, Celery workers, Redis queues, OAuth account linking, and SDKs for Python and JavaScript. The project now includes:

- `Posts`: publish or schedule content to multiple platforms from one request.
- `Videos`: trigger AI video generation through `yt-factory` and optionally auto-publish the result.
- `Content Bombs`: transform one topic into platform-specific variants with AI-assisted copy generation.
- `Comments`: collect comments and run AI-assisted reply workflows for supported platforms.
- `Predict`: score hooks, titles, and captions with viral heuristics plus A/B variant suggestions.
- `Schedules`: create timezone-aware recurring publish schedules with recommended posting windows.
- `Accounts`: connect OAuth providers and store tokens with AES-256 encryption.
- `Analytics`: fetch account-level and post-level performance summaries.
- `Usage`: expose billing-plan quotas and usage history for dashboarding.
- `SDKs`: first-party Python and JavaScript clients.
- `Landing`: production landing page and API docs site in `landing/`, deployed on Vercel.

## Supported Platforms

YouTube, TikTok, Instagram, X, LinkedIn, Facebook, Threads, Pinterest, Reddit, Bluesky, Snapchat, Telegram, WordPress, Google Business Profile, Naver Blog, Tistory, Kakao, and note.com.

## Quick Start

1. Create a local env file.

```bash
copy .env.example .env
```

2. Install backend dependencies.

```bash
pip install -e ".[dev]"
```

3. Start the full local stack.

```bash
docker compose up --build -d
```

4. Open the API docs.

```text
http://localhost:8000/docs
```

5. Run the quality checks.

```bash
ruff check .
pytest -q
```

## Docker Compose

`docker compose up --build -d` starts:

- `api`: FastAPI application on `http://localhost:8000`
- `worker`: Celery worker for post, video, bomb, comment, and schedule jobs
- `beat`: Celery Beat for periodic comment collection and schedule dispatch
- `redis`: broker and result backend

Useful commands:

```bash
docker compose ps
docker compose logs api --tail=100
docker compose down
```

## Local Development

Run the API without Docker:

```bash
uvicorn app.main:app --reload --port 8000
```

Run workers manually:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
celery -A app.workers.celery_app.celery_app beat --loglevel=INFO
```

Landing site:

```bash
cd landing
npm install
npm run dev
```

## SDK Installation

Python SDK:

```bash
pip install -e ./sdk/python
```

JavaScript / TypeScript SDK:

```bash
npm install contentflow-sdk
```

## API Examples

Create a post:

```bash
curl -X POST http://localhost:8000/api/v1/posts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cf_live_replace_me" \
  -d '{
    "text": "Launching our new campaign across every short-form channel.",
    "platforms": ["youtube", "tiktok", "instagram"],
    "media_urls": ["https://cdn.example.com/video.mp4"],
    "media_type": "video"
  }'
```

Generate a video with auto-publish:

```bash
curl -X POST http://localhost:8000/api/v1/videos/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cf_live_replace_me" \
  -d '{
    "topic": "AI marketing workflow",
    "mode": "marketing",
    "language": "en",
    "format": "shorts",
    "style": "cinematic",
    "auto_publish": {
      "enabled": true,
      "platforms": ["youtube", "tiktok"]
    }
  }'
```

Score a hook:

```bash
curl -X POST http://localhost:8000/api/v1/predict/viral-score \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cf_live_replace_me" \
  -d '{
    "platform": "youtube",
    "title": "I tested 18 platforms with one topic",
    "description": "Here is what scaled, what failed, and what changed the workflow."
  }'
```

Create a schedule:

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cf_live_replace_me" \
  -d '{
    "name": "weekday shorts",
    "platforms": ["youtube", "tiktok"],
    "timezone": "KST",
    "recurrence": "daily",
    "time_of_day": "18:30"
  }'
```

## Environment Variables

### App

- `APP_ENV`: runtime environment such as `development` or `production`
- `APP_NAME`: FastAPI application name
- `APP_HOST`: bind host for local server
- `APP_PORT`: bind port for local server
- `LOG_LEVEL`: application log verbosity

### Supabase

- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: optional public client key
- `SUPABASE_SERVICE_ROLE_KEY`: backend service-role key
- `SUPABASE_DB_URL`: direct Postgres connection string for migrations or bootstrap tasks

### Redis and Celery

- `REDIS_URL`: default Redis URL
- `CELERY_BROKER_URL`: Celery broker URL, defaults to `REDIS_URL`
- `CELERY_RESULT_BACKEND`: Celery result backend URL, defaults to broker URL

### API Keys and Auth

- `API_KEY_PREFIX`: generated API key prefix, usually `cf_live`
- `API_KEY_BYTES`: random-byte length used for key generation

### OAuth and Token Encryption

- `TOKEN_ENCRYPTION_KEY`: base64-encoded 32-byte AES-256 key
- `OAUTH_STATE_SECRET`: CSRF/state secret for OAuth redirects
- `OAUTH_REDIRECT_BASE_URL`: public base URL used to build OAuth callback URLs
- `TOKEN_REFRESH_LEEWAY_SECONDS`: refresh window before provider token expiry

### yt-factory Video Generation

- `YT_FACTORY_BASE_URL`: upstream video generation service base URL
- `YT_FACTORY_API_KEY`: API key for `yt-factory`
- `YT_FACTORY_TIMEOUT_SECONDS`: end-to-end generation timeout
- `YT_FACTORY_POLL_INTERVAL_SECONDS`: polling interval for generation status

### OAuth Provider Credentials

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `META_CLIENT_ID`
- `META_CLIENT_SECRET`
- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- `X_CLIENT_ID`
- `X_CLIENT_SECRET`

### AI Services

- `ANTHROPIC_API_KEY`: Claude API key for Content Bomb, Comments, and Predict flows
- `ANTHROPIC_MODEL`: default Claude model name
- `ANTHROPIC_API_BASE_URL`: Anthropic API base URL override
- `COMMENT_POLL_INTERVAL_SECONDS`: background polling interval for comment collection

### Deployment

- `RAILWAY_ENVIRONMENT`: deployment environment label used by Railway-oriented config

## API Surface

Main route groups:

- `/api/v1/posts`
- `/api/v1/videos`
- `/api/v1/bombs`
- `/api/v1/comments`
- `/api/v1/predict`
- `/api/v1/schedules`
- `/api/v1/usage`
- `/api/v1/accounts`
- `/api/v1/analytics`

Interactive docs:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Deployment Notes

- Landing site root: `landing/`
- Production site: `https://contentflow-lovat.vercel.app`
- API docs page in landing app: `https://contentflow-lovat.vercel.app/docs`

## Testing

```bash
ruff check .
pytest -q
```
