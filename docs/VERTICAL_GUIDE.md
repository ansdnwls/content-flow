# Vertical Product Guide

## Overview

The Vertical Launcher lets you create niche products on top of the ContentFlow engine in minutes. Each vertical shares the same backend (API, adapters, billing) but has its own branding, landing page, dashboard, and feature set.

## Quick Start

### 1. Create a new vertical

```bash
cd tools/create-vertical
npx tsx src/index.ts
```

The CLI will prompt you for:
- Vertical ID (e.g., `ytboost`)
- Display name (e.g., `YtBoost`)
- Tagline
- Brand color
- Currency
- Hero platforms

### 2. Configure `config.json`

Every vertical is defined by a single `config.json` file:

```
verticals/<name>/config.json
```

Key sections:
- **brand** — Logo, colors, fonts
- **domain** — Primary, API, and docs domains
- **target** — Persona, pain points, languages, regions
- **pricing** — Currency and plan tiers
- **features** — Core features, enabled/hero/hidden platforms
- **landing** — Hero text, section order
- **dashboard** — Home widgets, navigation, onboarding steps

The schema is at `packages/cf-config/schema.json`.

### 3. Add custom widgets (optional)

If your vertical needs specialized dashboard widgets:

```
verticals/<name>/widgets/MyCustomWidget.tsx
```

Import and add to the `WIDGET_MAP` in `dashboard/app/page.tsx`.

### 4. Customize landing sections (optional)

Override or add sections in `verticals/<name>/landing/app/page.tsx`.

### 5. Add presets

Create workflow presets in `verticals/<name>/presets/`:

```json
{
  "id": "my_workflow",
  "name": "My Workflow",
  "trigger": { "type": "manual" },
  "pipeline": [
    { "step": "create_post" },
    { "step": "distribute", "platforms": ["youtube", "tiktok"] }
  ]
}
```

### 6. Local development

```bash
cd verticals/<name>/landing && npm install && npm run dev
cd verticals/<name>/dashboard && npm install && npm run dev
```

### 7. Deploy

Push to `main` branch. GitHub Actions (`deploy-vertical.yml`) auto-detects changed verticals and deploys only what changed.

## Architecture

```
verticals/<name>/
├── config.json          # Single source of truth
├── vercel.json          # Deployment config
├── landing/             # Next.js landing page
│   └── app/page.tsx     # Reads config.json for sections
├── dashboard/           # Next.js dashboard
│   ├── app/page.tsx     # Reads config.json for widgets
│   └── components/      # Config-driven sidebar
├── presets/             # Workflow presets
├── widgets/             # Custom widgets (optional)
└── assets/              # Logo, favicon, images
```

## Shared Packages

| Package | Purpose |
|---------|---------|
| `@contentflow/config` | TypeScript types, JSON schema, utilities |
| `@contentflow/ui` | Shared React components (Hero, Pricing, FAQ, widgets) |
| `@contentflow/engine` | ContentFlow API client wrapper |

## Backend Connection

Each vertical's dashboard connects to the ContentFlow API via `@contentflow/engine`.

### Configuration

Add a `backend` section to `config.json`:

```json
{
  "backend": {
    "base_url": "https://api.yourvertical.dev",
    "api_version": "v1"
  }
}
```

### Environment Variables

| Variable | Scope | Description |
|----------|-------|-------------|
| `NEXT_PUBLIC_CF_API_URL` | Client + Server | ContentFlow API base URL (overrides config.json) |
| `CF_API_KEY` | Server only | API key for server-side data fetching |

Priority: `NEXT_PUBLIC_CF_API_URL` > `config.json backend.base_url` > `http://localhost:8000`

### Dashboard API Client

Each vertical has a `dashboard/lib/api.ts` that initializes a shared `CFEngine` instance:

```typescript
import { CFEngine } from "@contentflow/engine";
import config from "../../config.json";

const API_URL = process.env.NEXT_PUBLIC_CF_API_URL ?? config.backend?.base_url ?? "http://localhost:8000";
const API_KEY = process.env.CF_API_KEY ?? "";

export const engine = new CFEngine({ apiUrl: API_URL, apiKey: API_KEY, config });
```

### Available API Methods

**General** (all verticals):
- `engine.getPosts()` / `engine.createPost()`
- `engine.getAccounts()` / `engine.getUsage()` / `engine.getAnalytics()`

**YtBoost**:
- `engine.listChannels()` / `engine.subscribeChannel()`
- `engine.listShorts()` / `engine.extractShorts()` / `engine.approveShort()`
- `engine.listPendingComments()` / `engine.approveComment()`

**ShopSync**:
- `engine.listProducts()` / `engine.createProduct()` / `engine.publishProduct()`

### Local Development with Backend

```bash
# Start the API server
cd /path/to/content-flow && uvicorn app.main:app --reload

# Start the dashboard with API connection
cd verticals/ytboost/dashboard
NEXT_PUBLIC_CF_API_URL=http://localhost:8000 CF_API_KEY=cf_live_xxx npm run dev
```

## Existing Verticals

| Vertical | Target | Domain | Backend |
|----------|--------|--------|---------|
| ytboost | YouTube creators (1K-100K subs) | ytboost.dev | api.ytboost.dev |
| shopsync | Ecommerce sellers (SmartStore, Coupang) | shopsync.kr | api.shopsync.kr |
