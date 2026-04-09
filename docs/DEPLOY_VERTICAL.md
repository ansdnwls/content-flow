# Deploying a Vertical to Vercel

Step-by-step guide for deploying ContentFlow verticals (YtBoost, ShopSync, etc.).

## Prerequisites

- Vercel account with CLI installed (`npm i -g vercel`)
- Access to the ContentFlow API (API key)
- Domain registered and DNS accessible

## 1. Vercel Project Setup

```bash
# From the vertical directory
cd verticals/ytboost

# Link to Vercel (creates .vercel/ directory)
vercel link
```

When prompted:
- **Which scope?** → Select your organization
- **Link to existing project?** → No (first time) or Yes (subsequent)
- **Project name?** → `ytboost` (or `shopsync`)
- **Root directory?** → `.` (current directory)

## 2. Environment Variables

Set required variables in the Vercel dashboard or CLI:

```bash
# Public variables (exposed to browser)
vercel env add NEXT_PUBLIC_CF_API_URL production
# → https://api.ytboost.dev

vercel env add NEXT_PUBLIC_CF_BRAND_NAME production
# → YtBoost

vercel env add NEXT_PUBLIC_CF_PRIMARY_COLOR production
# → #FF0000

# Server-side only (never exposed to browser)
vercel env add CF_API_KEY production
# → cf_live_xxxxxxxxxxxx
```

For preview deployments, add the same variables with `preview` scope:

```bash
vercel env add NEXT_PUBLIC_CF_API_URL preview
# → https://api-staging.ytboost.dev
```

### Pre-build Validation

Run the environment checker before deploying:

```bash
python scripts/check_vertical_env.py verticals/ytboost
```

## 3. Domain Configuration

### Add Custom Domain

```bash
vercel domains add ytboost.dev
vercel domains add www.ytboost.dev
```

### DNS Records

| Type  | Name | Value                        |
|-------|------|------------------------------|
| A     | @    | 76.76.21.21                  |
| CNAME | www  | cname.vercel-dns.com         |
| CNAME | api  | your-api-server.railway.app  |

Wait for DNS propagation (up to 48h, usually minutes).

### Verify Domain

```bash
vercel domains inspect ytboost.dev
```

## 4. Deploy

### Automatic (CI/CD)

Pushes to `main` that modify `verticals/<name>/**` trigger automatic deployment
via `.github/workflows/deploy-vertical.yml`.

### Manual

```bash
# Preview deployment
cd verticals/ytboost
vercel

# Production deployment
vercel --prod
```

## 5. Preview Deployments

Every PR that touches `verticals/<name>/` gets a preview URL:

- `https://ytboost-<hash>.vercel.app`
- Accessible via the PR comment from Vercel bot

To configure per-branch environment variables:

```bash
vercel env add NEXT_PUBLIC_CF_API_URL preview
# → https://api-staging.ytboost.dev
```

## 6. Rollback

### Via Vercel Dashboard

1. Go to **Project → Deployments**
2. Find the last working deployment
3. Click **⋯ → Promote to Production**

### Via CLI

```bash
# List recent deployments
vercel ls ytboost

# Rollback to a specific deployment
vercel promote <deployment-url>
```

### Emergency Rollback

```bash
# Instant rollback to previous production deployment
vercel rollback
```

## Vertical Domains Reference

| Vertical | Production       | API                  | Docs                  |
|----------|------------------|----------------------|-----------------------|
| YtBoost  | ytboost.dev      | api.ytboost.dev      | docs.ytboost.dev      |
| ShopSync | shopsync.kr      | api.shopsync.kr      | docs.shopsync.kr      |

## Troubleshooting

### Build Fails

1. Check build logs: `vercel logs <deployment-url>`
2. Verify environment variables are set: `vercel env ls`
3. Test build locally: `cd verticals/ytboost/dashboard && pnpm build`

### Domain Not Resolving

1. Check DNS propagation: `dig ytboost.dev`
2. Verify domain in Vercel: `vercel domains inspect ytboost.dev`
3. Ensure SSL certificate is provisioned (automatic, may take a few minutes)

### API Proxy Not Working

1. Check `vercel.json` rewrites configuration
2. Verify the API backend is accessible
3. Check CORS headers on the API server
