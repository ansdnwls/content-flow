# ContentFlow Go SDK

Go client library for the [ContentFlow API](https://contentflow-api.railway.app).

## Installation

```bash
go get github.com/ansdnwls/content-flow/sdk/go
```

## Quick Start

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

    // Create a multi-platform post
    text := "Hello from Go SDK!"
    post, err := client.Posts.Create(ctx, &cf.CreatePostRequest{
        Text:      &text,
        Platforms: []string{"youtube", "tiktok", "instagram"},
    })
    if err != nil {
        log.Fatal(err)
    }
    fmt.Printf("Post created: %s (status: %s)\n", post.ID, post.Status)
}
```

## Resources

| Resource | Methods |
|----------|---------|
| `Posts` | `Create`, `Get`, `List`, `Cancel` |
| `Videos` | `Generate`, `Get` |
| `Accounts` | `List`, `Connect`, `Disconnect` |
| `Analytics` | `Dashboard`, `Summary`, `Platforms`, `TopPosts`, `Growth` |
| `Comments` | `Collect`, `List`, `Get`, `Reply` |
| `Bombs` | `Create`, `Get`, `Publish` |
| `Webhooks` | `ListDeliveries`, `ListDeadLetters`, `Redeliver`, `Replay` |

## Client Options

```go
// Custom base URL
client := cf.New("key", cf.WithBaseURL("http://localhost:8000"))

// Custom timeout
client := cf.New("key", cf.WithTimeout(60 * time.Second))

// Custom HTTP client
client := cf.New("key", cf.WithHTTPClient(&http.Client{
    Transport: &http.Transport{MaxIdleConns: 100},
}))
```

## Error Handling

```go
post, err := client.Posts.Get(ctx, "post-1")
if err != nil {
    var authErr *cf.AuthError
    var rlErr   *cf.RateLimitError
    var apiErr  *cf.APIError

    switch {
    case errors.As(err, &authErr):
        log.Fatal("invalid API key")
    case errors.As(err, &rlErr):
        log.Printf("rate limited, retry after %s", rlErr.RetryAfter)
    case errors.As(err, &apiErr):
        log.Printf("API error %d: %s", apiErr.StatusCode, apiErr.Detail)
    default:
        log.Fatal(err)
    }
}
```

## Webhook Signature Verification

```go
func webhookHandler(w http.ResponseWriter, r *http.Request) {
    body, _ := io.ReadAll(r.Body)
    signature := r.Header.Get("X-ContentFlow-Signature")
    timestamp := r.Header.Get("X-ContentFlow-Timestamp")

    if err := cf.VerifySignature(body, signature, timestamp, "whsec_xxx"); err != nil {
        http.Error(w, "invalid signature", 401)
        return
    }
    // Process the event
}
```

## Testing

```bash
go test ./contentflow/ -v
```
