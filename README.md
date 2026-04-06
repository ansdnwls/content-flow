# ContentFlow API

> Social Media Posting + AI Video Generation API.
> One API call. 14+ platforms. Generate and distribute content at scale.

## What is ContentFlow?

```
Zernio:       Content (you provide) → Distribution API
ContentFlow:  One topic → AI Video Generation → Distribution API
```

ContentFlow does everything Zernio does (multi-platform posting, scheduling, analytics)
**plus** AI-powered video generation from a single topic.

## Quick Start

```python
from contentflow import ContentFlow

cf = ContentFlow(api_key="cf_live_xxx")

# Post to multiple platforms at once
post = cf.posts.create(
    text="New video drop!",
    platforms=["youtube", "tiktok", "instagram"],
    media_urls=["https://example.com/video.mp4"],
    scheduled_for="2026-04-07T09:00:00Z"
)

# Or generate a video AND publish — one call
video = cf.videos.generate(
    topic="The truth about DUI 3-strike laws",
    mode="legal",
    language="ko",
    format="shorts",
    auto_publish={"platforms": ["youtube", "tiktok"]}
)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/posts` | Create/schedule posts |
| GET | `/api/v1/posts/{id}` | Get post status |
| POST | `/api/v1/videos/generate` | Generate AI video |
| GET | `/api/v1/videos/{id}` | Get video status |
| GET | `/api/v1/accounts` | List connected accounts |
| POST | `/api/v1/accounts/connect/{platform}` | Connect via OAuth |
| GET | `/api/v1/analytics` | Unified analytics |
| POST | `/api/v1/webhooks` | Register webhook |

## Supported Platforms

YouTube · TikTok · Instagram · Facebook · X/Twitter · LinkedIn
Threads · Pinterest · Reddit · Bluesky · Telegram · WordPress
Snapchat · Google Business

## Pricing

| Plan | Price | Social Sets | Posts/mo | Video Gen/mo |
|------|-------|------------|---------|-------------|
| Free | $0 | 2 | 20 | 3 |
| Build | $29/mo | 5 | 200 | 20 |
| Scale | $79/mo | 20 | Unlimited | 100 |
| Enterprise | $299/mo | Unlimited | Unlimited | Unlimited |

## Tech Stack

- **API**: FastAPI (Python 3.11)
- **DB**: Supabase (PostgreSQL)
- **Queue**: Redis + Celery
- **Video Engine**: yt-factory
- **Hosting**: Railway / Fly.io
- **Frontend**: Next.js (Vercel)

## Development

```bash
# Setup
cp .env.example .env
pip install -e ".[dev]"

# Run
uvicorn app.main:app --reload --port 8000

# Test
pytest tests/ -v
```

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [API Spec](docs/API_SPEC.md)
- [Pricing](docs/PRICING.md)

## License

Proprietary — © 2026 ContentFlow
