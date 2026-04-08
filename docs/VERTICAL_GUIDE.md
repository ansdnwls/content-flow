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

## Existing Verticals

| Vertical | Target | Domain |
|----------|--------|--------|
| ytboost | YouTube creators (1K-100K subs) | ytboost.dev |
| shopsync | Ecommerce sellers (SmartStore, Coupang) | shopsync.kr |
