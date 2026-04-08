# ContentFlow Verticals

Niche products built on top of the ContentFlow engine.

## Verticals

| Vertical | Status | Domain | Target |
|----------|--------|--------|--------|
| ytboost | Development | ytboost.dev | YouTube creators (1K-100K subscribers) |
| shopsync | Development | shopsync.kr | Ecommerce sellers (SmartStore, Coupang, 11st) |

## Creating a New Vertical

```bash
cd tools/create-vertical
npx tsx src/index.ts
```

See [docs/VERTICAL_GUIDE.md](../docs/VERTICAL_GUIDE.md) for the full guide.

## Directory Structure

```
verticals/
├── _template/     # Base template (do not deploy)
├── ytboost/       # YouTube creator amplifier
└── shopsync/      # Ecommerce seller autopilot
```

## Shared Packages

All verticals use shared packages from `packages/`:
- `@contentflow/config` — Types and schema
- `@contentflow/ui` — React components
- `@contentflow/engine` — API client
