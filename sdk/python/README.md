# ContentFlow Python SDK

Python client for the [ContentFlow API](https://api.contentflow.dev) — multi-platform social posting + AI video generation.

## Install

```bash
pip install contentflow
```

## Quick Start

### Synchronous

```python
from contentflow import ContentFlow

cf = ContentFlow(api_key="cf_live_xxx")

# Post to multiple platforms
post = cf.posts.create(
    text="New video drop!",
    platforms=["youtube", "tiktok", "instagram"],
    media_urls=["https://example.com/video.mp4"],
    media_type="video",
)
print(post["id"], post["status"])

# Get post status
post = cf.posts.get(post["id"])

# List posts
result = cf.posts.list(page=1, limit=10, status="published")

# Cancel a scheduled post
cf.posts.cancel(post["id"])

# Generate AI video
video = cf.videos.generate(
    topic="The truth about DUI 3-strike laws",
    mode="legal",
    language="ko",
    auto_publish={"platforms": ["youtube", "tiktok"]},
)

# List connected accounts
accounts = cf.accounts.list()

# Get analytics
analytics = cf.analytics.get()
analytics_yt = cf.analytics.get(platform="youtube")
```

### Asynchronous

```python
from contentflow import AsyncContentFlow

async with AsyncContentFlow(api_key="cf_live_xxx") as cf:
    post = await cf.posts.create(
        text="Hello!",
        platforms=["youtube", "tiktok"],
    )
```

## Configuration

```python
cf = ContentFlow(
    api_key="cf_live_xxx",
    base_url="https://api.contentflow.dev",  # custom base URL
    timeout=30.0,                             # request timeout in seconds
)
```

## License

MIT
