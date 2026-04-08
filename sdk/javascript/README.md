# ContentFlow JavaScript/TypeScript SDK

Official JavaScript/TypeScript client for the [ContentFlow API](https://github.com/ansdnwls/content-flow) — multi-platform social media posting, AI video generation, comment autopilot, and content bombs.

## Installation

```bash
npm install contentflow-sdk
```

## Quick Start

```typescript
import { ContentFlow } from "contentflow-sdk";

const cf = new ContentFlow({ apiKey: "cf_live_xxx" });

// Create a multi-platform post
const post = await cf.posts.create({
  text: "Hello from ContentFlow!",
  platforms: ["youtube", "tiktok", "instagram"],
  mediaUrls: ["https://example.com/video.mp4"],
});

console.log(post);
```

## Resources

### Posts

```typescript
// Create a post
const post = await cf.posts.create({
  text: "New video is live!",
  platforms: ["youtube", "tiktok"],
  mediaUrls: ["https://cdn.example.com/video.mp4"],
  mediaType: "video",
  scheduledFor: "2026-04-10T09:00:00+09:00",
  platformOptions: {
    youtube: { title: "My Video", privacy: "public" },
  },
});

// Get post status
const status = await cf.posts.get("post_id");

// List posts
const list = await cf.posts.list({ page: 1, limit: 20, status: "published" });

// Cancel a pending post
const cancelled = await cf.posts.cancel("post_id");
```

### Videos

```typescript
// Generate an AI video
const video = await cf.videos.generate({
  topic: "DUI 3-strike laws",
  mode: "legal",
  language: "ko",
  format: "shorts",
  style: "realistic",
  autoPublish: { enabled: true, platforms: ["youtube"] },
});

// Check generation status
const job = await cf.videos.get("video_id");
```

### Accounts

```typescript
// List connected social accounts
const accounts = await cf.accounts.list();

// Start OAuth connection
const oauth = await cf.accounts.connect("youtube");
// Redirect user to oauth.authorize_url
```

### Analytics

```typescript
// Get unified analytics
const analytics = await cf.analytics.get();

// Get platform-specific analytics
const ytAnalytics = await cf.analytics.get("youtube");
```

### Comments (Comment Autopilot)

```typescript
// Collect comments from a platform post
const comments = await cf.comments.collect({
  platform: "youtube",
  platformPostId: "abc123",
  credentials: { access_token: "ya29..." },
});

// List collected comments
const list = await cf.comments.list({
  platform: "youtube",
  replyStatus: "pending",
});

// Get a single comment
const comment = await cf.comments.get("comment_id");

// AI auto-reply to a comment
const reply = await cf.comments.reply("comment_id", {
  credentials: { access_token: "ya29..." },
  context: "Video about Python tips",
});
```

### Content Bombs

```typescript
// Create a content bomb (generates platform-specific variants)
const bomb = await cf.bombs.create({ topic: "DUI 3-strike laws" });

// Check transformation status
const status = await cf.bombs.get("bomb_id");

// Publish all variants
const published = await cf.bombs.publish("bomb_id");
```

## Configuration

```typescript
const cf = new ContentFlow({
  apiKey: "cf_live_xxx",       // Required
  baseUrl: "https://custom.api.dev", // Default: https://api.contentflow.dev
  timeout: 60000,              // Default: 30000ms
});
```

## Error Handling

```typescript
import { ContentFlow, ContentFlowError } from "contentflow-sdk";

try {
  await cf.posts.create({ platforms: ["youtube"], text: "Hello" });
} catch (e) {
  if (e instanceof ContentFlowError) {
    console.error(`API Error ${e.status}: ${e.message}`);
    console.error("Response body:", e.body);
  }
}
```

## Requirements

- Node.js >= 18 (uses native `fetch`)
- Works in modern browsers

## License

MIT
