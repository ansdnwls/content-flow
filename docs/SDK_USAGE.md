# ContentFlow SDK Usage Guide

Client libraries for the ContentFlow API in Python, JavaScript/TypeScript, and Go.

## Python

### Installation

```bash
pip install contentflow
# or from source
pip install -e sdk/python
```

### Quick Start

```python
from contentflow import ContentFlow

cf = ContentFlow(api_key="cf_live_xxx")

# Create a post
post = cf.posts.create(
    text="Hello world!",
    platforms=["youtube", "tiktok"],
)
print(post["id"], post["status"])

# List posts
posts = cf.posts.list(page=1, limit=10, status="published")
for p in posts["data"]:
    print(p["id"], p["status"])

# Generate a video
video = cf.videos.generate(topic="Python tips", format="shorts")
print(video["id"])

# Get analytics
analytics = cf.analytics.get()
print(analytics)

# List connected accounts
accounts = cf.accounts.list()
print(accounts)
```

### Async Client

```python
import asyncio
from contentflow import AsyncContentFlow

async def main():
    async with AsyncContentFlow(api_key="cf_live_xxx") as cf:
        post = await cf.posts.create(
            text="Async post!",
            platforms=["youtube"],
        )
        print(post)

asyncio.run(main())
```

### Webhook Verification

```python
from contentflow import webhooks

is_valid = webhooks.verify_signature(
    payload=request_body,
    signature=request.headers["X-CF-Signature"],
    secret="whsec_your_webhook_secret",
)
```

### Type Hints (Pydantic)

```python
from contentflow.types import Post, PostList, Video

# Parse raw API response into typed model
post = Post(**raw_response)
print(post.id, post.status, post.created_at)
```

### Custom Exceptions

```python
from contentflow.exceptions import APIError, AuthenticationError, RateLimitError

try:
    cf.posts.get("nonexistent-id")
except AuthenticationError:
    print("Bad API key")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
```

---

## JavaScript / TypeScript

### Installation

```bash
npm install contentflow-sdk
# or from source
cd sdk/javascript && npm install && npm run build
```

### Quick Start

```typescript
import ContentFlow from "contentflow-sdk";

const cf = new ContentFlow({ apiKey: "cf_live_xxx" });

// Create a post
const post = await cf.posts.create({
  text: "Hello from JS!",
  platforms: ["youtube", "tiktok"],
});
console.log(post);

// Generate a video
const video = await cf.videos.generate({ topic: "TypeScript tips" });
console.log(video);

// List connected accounts
const accounts = await cf.accounts.list();
console.log(accounts);

// Get analytics
const analytics = await cf.analytics.get();
console.log(analytics);
```

### Webhook Verification

```typescript
import { verifySignature } from "contentflow-sdk";

const isValid = await verifySignature({
  payload: rawBody,
  signature: headers["x-cf-signature"],
  secret: "whsec_your_webhook_secret",
});
```

### Type Imports

```typescript
import type { Post, PostList, Video, Account } from "contentflow-sdk/types";
```

### Error Handling

```typescript
import { ContentFlowError } from "contentflow-sdk";

try {
  await cf.posts.get("nonexistent-id");
} catch (err) {
  if (err instanceof ContentFlowError) {
    console.error(`API error ${err.status}: ${err.message}`);
  }
}
```

---

## Go

### Installation

```bash
go get github.com/ansdnwls/content-flow/sdk/go/contentflow
```

### Quick Start

```go
package main

import (
    "context"
    "fmt"
    "log"

    cf "github.com/ansdnwls/content-flow/sdk/go/contentflow"
)

func main() {
    client := cf.New("cf_live_xxx")

    ctx := context.Background()

    // Create a post
    text := "Hello from Go!"
    post, err := client.Posts.Create(ctx, &cf.CreatePostRequest{
        Text:      &text,
        Platforms: []string{"youtube", "tiktok"},
    })
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(post.ID, post.Status)

    // List posts
    posts, err := client.Posts.List(ctx, &cf.ListPostsParams{
        Page:  1,
        Limit: 10,
    })
    if err != nil {
        log.Fatal(err)
    }
    for _, p := range posts.Data {
        fmt.Println(p.ID, p.Status)
    }

    // Generate a video
    video, err := client.Videos.Generate(ctx, &cf.GenerateVideoRequest{
        Topic: "Go tips",
    })
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(video.ID)

    // List accounts
    accounts, err := client.Accounts.List(ctx)
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(accounts.Total)
}
```

### Webhook Verification

```go
import cf "github.com/ansdnwls/content-flow/sdk/go/contentflow"

valid := cf.VerifySignature(payload, signature, secret)
```

### Error Handling

```go
_, err := client.Posts.Get(ctx, "nonexistent-id")
if err != nil {
    var apiErr *cf.APIError
    if errors.As(err, &apiErr) {
        fmt.Printf("HTTP %d: %s\n", apiErr.StatusCode, apiErr.Detail)
    }

    var authErr *cf.AuthError
    if errors.As(err, &authErr) {
        fmt.Println("Invalid API key")
    }

    var rateErr *cf.RateLimitError
    if errors.As(err, &rateErr) {
        fmt.Printf("Rate limited, retry after %s\n", rateErr.RetryAfter)
    }
}
```

### Client Options

```go
client := cf.New("cf_live_xxx",
    cf.WithBaseURL("https://api-staging.contentflow.dev"),
    cf.WithTimeout(10 * time.Second),
)
```

---

## Common Patterns

### Pagination

All list endpoints return paginated responses with `total`, `page`, and `limit` fields.

### Rate Limiting

The API returns `429 Too Many Requests` with a `Retry-After` header. All SDKs surface this as a typed error with the retry-after value.

### Authentication

Pass your API key when creating the client. The key is sent as `X-API-Key` header on every request. Never expose your API key in client-side code.
