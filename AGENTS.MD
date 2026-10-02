# Repository Guidelines

Use `rtk` for shell commands. Use Klassify for GitHub issues and authorized commits. Write relative paths in docs. Browser testing uses Codex's in-app browser; close resources immediately afterward. Do not introduce shims/barrel exports for decomposition.

## Stack and ownership

Read [architecture](docs/architecture.md) first. Bun workspace: `apps/web/` (React/Vite), `apps/worker/` (Workers/Better Auth/D1/R2/Workflow), `packages/contracts/` (public TS types), `packages/engine/` (Python/OpenCV/PyMuPDF native Container and CLI).

Use type aliases, arrow functions and `Foo[]` in frontend code. Public contracts live in `packages/contracts/src/types.ts`; declare imports directly without barrel files. Generate Worker binding/runtime types with `bun run worker:types`; do not hand-edit `apps/worker/env.d.ts`. Python 3.14.7 is pinned in Docker and dependencies are locked in the engine package.

## Invariants

- Every job/artifact access is owner-scoped and expiration-aware.
- Session-only key issuance/rotation; store hashes, show plaintext once.
- Cookie mutations require exact origin; retain Better Auth persistent rate limits.
- Native CV stays outside Worker memory. Preserve canonical renderer and original page numbering.
- Upload actual byte/pixel/page/output limits stay enforced.
- Commit page receipts only after JSON and image exist; derive progress from receipts.
- R2 originals are durable; engine files are disposable caches.
- Use additive D1 migrations and compatible container protocols.
- Preserve remote auth secrets. Never treat auth/network errors as missing secrets.
- Never expose an engine route or put secrets in assets/docs/logs.

## Operations

`bun run dev` starts local Worker/services and native Python using the local-only root Wrangler config. `bun run deploy` uses `cf` and `apps/worker/cloudflare.config.ts` for authenticated one-shot provisioning/build/migrations/deployment/verification at `skalu.ilmtest.net`. Google Cloud configuration is retired.

## Validation and releases

Use focused checks while editing, then run appropriate stable-source integration checks. See [TESTING.md](TESTING.md). Avoid editing Worker source during E2E runs. CI covers types/lint/Bun/native tests/build/Playwright. Release Please tracks app and engine versions; conventional commits determine semantic versions. `bun run types:generate` emits public declarations.

For authorized commits, use `klassify git commit` directly (RTK exception). Do not commit/push without authorization.
