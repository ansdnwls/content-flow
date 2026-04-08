# ContentFlow Docs Site

Mintlify documentation project for `docs.contentflow.dev`.

## Local development

```bash
cd docs-site
npm install
npm run dev
```

## Production build validation

```bash
cd docs-site
npm run build
```

The build script does three things:

1. Regenerates `docs/openapi.json` from the FastAPI app.
2. Copies that file into `docs-site/openapi.json`.
3. Runs Mintlify OpenAPI validation plus docs validation and link checks.

## Deployment

Primary path: Mintlify Cloud.

1. Create a Mintlify project and connect this repository.
2. Set the project root to `docs-site/`.
3. Set the custom domain to `docs.contentflow.dev`.
4. Keep `npm run build` as the validation command in CI.

Fallback path: Vercel previews can still run `npm run build` for validation, but production hosting is cleaner on Mintlify Cloud because it natively serves the generated API reference from `openapi.json`.
