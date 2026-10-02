# Skalu

Private PDF structure extraction on Cloudflare. Create an account, issue/rotate an API key, drop a PDF, inspect detected lines and rectangles as pages finish, and download JSON.

## Stack and layout

- `apps/web/`: React 19/Vite workbench. SSR adds no value to this authenticated application.
- `apps/worker/`: TypeScript 7, Better Auth, job API, Workflow and cleanup.
- `packages/engine/`: Python 3.14.7, OpenCV/PyMuPDF/Pillow in a private Cloudflare Container; shared CLI/service renderer.
- `packages/contracts/`: public contracts and detection validation.
- `migrations/`, `scripts/`, `e2e/`: D1 schema, operations and real Playwright acceptance tests.

See [architecture](docs/architecture.md) and [testing](TESTING.md).

## Local development

Install Bun 1.4.2+, Node 26+ and [uv](https://docs.astral.sh/uv/getting-started/installation/):

```sh
bun install --frozen-lockfile
bun run dev
```

Open `http://localhost:8787`. Startup installs locked Python dependencies, builds the webapp, generates private local secrets, applies local D1 migrations and starts Wrangler plus native Python. D1/R2/Workflows are emulated; processing is real. Docker is unnecessary for this development path. Ctrl-C closes both services.

## One-command deployment

Prerequisites: authenticated `cf` (`cf login`), Docker with Linux amd64 build support, and **Workers Paid** with Containers, Workflows, D1 and R2 enabled. The website Pro plan and Workers Paid are separate subscriptions. Nothing upgrades billing automatically.

On macOS, Docker Desktop works, or install the smaller Colima builder:

```sh
brew install docker docker-buildx colima
```

Register Homebrew's Docker CLI plugin directory following `brew info docker-buildx`. Deployment automatically starts an isolated `skalu` Colima profile with no host mounts when no Docker engine is running, and stops it afterward. It never changes your default Docker context. If an engine is already running, deployment uses it.

```sh
bun install --frozen-lockfile
bun run deploy
```

The command checks authentication/Docker before remote changes, runs checks, prebuilds the native image, provisions the `skalu` D1 database and `skalu-files` R2 bucket if missing, adds retention rules and applies migrations before deployment. `cf deploy` deploys the Worker, assets, Workflow and container together at **https://skalu.ilmtest.net**, including managed DNS and TLS. Success requires a protected live check of D1/R2 and matching app/engine versions.

The `ilmtest.net` zone must belong to the authenticated account. Set `CLOUDFLARE_ACCOUNT_ID` for multiple memberships. The production origin and custom domain live in `apps/worker/cloudflare.config.ts`; `workers.dev` and preview URLs are disabled. Local development still uses `http://localhost:8787`.

`apps/worker/wrangler.config.ts` configures the bundler used by `cf`. Root `wrangler.jsonc` is only for Docker-free local emulation and runtime type generation; it contains no production domain or container configuration. Provisioned IDs and build metadata are generated in `.cloudflare/deploy-state.json`. Generated production auth secrets are saved in `.cloudflare/production-secrets.json` with mode 0600; back this up privately. Existing remote auth secrets are preserved, including deployments from another checkout. Auth/network/parse errors never trigger secret replacement. The deployment-check token is operational access deliberately renewed per deploy; its temporary file is removed afterward. Secrets never enter the browser bundle.

Docker packages Python and its native PDF/image libraries for Cloudflare Containers. It is needed to build this engine, not to run the frontend or local Python development. Cloudflare runs the uploaded image; your local builder can stop after deployment. Diagnose rollout with `cf containers applications list` and `cf workflows instances list --workflow-name skalu-analysis`. Retain prior container images for rollback; code rollback does not restore D1/R2 data.

If a newly created hostname temporarily fails to resolve, compare `dig @1.1.1.1 skalu.ilmtest.net` with your system resolver and check `curl https://skalu.ilmtest.net/version`. `ping` takes a hostname (`ping skalu.ilmtest.net`), not an HTTPS URL; HTTPS is the useful application check.

## Accounts and privacy

Better Auth stores password hashes/sessions in D1. Passwords require 12–128 characters. Email is a sign-in identifier; this release does not send verification or password-recovery emails and never treats an address as verified identity. Ownership uses immutable user IDs. Keep your password in a password manager.

Browser mutations require the exact configured origin. API keys are random bearer credentials; only SHA-256 hashes and display prefixes persist. Key issuance/rotation requires a browser session; bearer access cannot mint replacements. Copy keys immediately: plaintext is shown once.

R2 is private. All status/image/page/download/deletion endpoints verify ownership. Documents expire 24 hours after completion/failure; uploads after one hour; processing has a two-hour deadline. Cron runs every 15 minutes. R2 lifecycle provides a two-day storage backstop and aborts unfinished multipart uploads after one day. Delete/cancel immediately revokes artifact access. Processing capacity stays reserved until the Workflow and native engine are confirmed stopped; failed cleanup is retried by cron. Seven-day tombstones sweep interrupted writes.

## Limits

Sequential **8 MiB upload parts** keep large PDFs below single-request/body budgets. Maximum PDF size: **256 MiB**; page count: **1,000**; render size: **16 megapixels/page**, **one billion pixels/document**, at 144 DPI. Invalid/encrypted/oversized PDFs receive explicit errors. Split documents beyond these ceilings before upload.

Each original page is a retryable Workflow step. JSON/JPEG artifacts reach R2 before progress is published, and the browser polls every two seconds. Native parsing/rendering run in killable subprocesses with CPU/memory/wall limits. Container files are disposable caches, reloaded from R2 after restart. Downloads stream page JSON with backpressure and reject incomplete jobs.

Admission is atomic: one active job and 20 submissions per rolling day per account, three active jobs globally. Four containers cover jobs plus deployment checks. Containers stop after cache release or sleep after two idle minutes. Increase quotas only with capacity and load testing.

These application budgets account for current [Worker limits](https://developers.cloudflare.com/workers/platform/limits/), [Workflow limits](https://developers.cloudflare.com/workflows/reference/limits/) and [Container limits](https://developers.cloudflare.com/containers/platform/limits/). Workers currently have 128 MB memory; Pro-zone request bodies are limited to 100 MB. PDF rendering runs in native containers rather than that isolate.

## API

API v2 is asynchronous. The public synchronous `/analyze` and server-side URL-ingestion endpoints have been removed. Job endpoints accept `Authorization: Bearer sk_...` or browser sessions. Cookie-authenticated mutations also require the configured `Origin`. Cross-origin browser access is disabled.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/health`, `/version` | Public health/release metadata |
| POST | `/api/auth/sign-up/email`, `/api/auth/sign-in/email` | Better Auth accounts/sessions |
| GET / POST | `/api/key` | Prefix / initial issuance; session only |
| POST | `/api/key/rotate` | Replace key atomically; session only |
| POST | `/api/jobs` | JSON `{filename,size,detection_params?}`; returns `{id,part_bytes}` |
| PUT | `/api/jobs/:id/parts/:number` | Raw bytes, exact Content-Length; part numbers start at 1 |
| POST | `/api/jobs/:id/start` | Complete upload and enqueue once; returns 202 |
| GET | `/api/jobs` | Latest 20 owned unexpired jobs |
| GET | `/api/jobs/:id` | Status/progress/errors and ordered artifact URLs |
| GET | `/api/jobs/:id/pages/:page` | Committed page JSON |
| GET | `/api/jobs/:id/pages/:page/image` | Detected-page JPEG |
| GET | `/api/jobs/:id/download` | Completed streamed JSON attachment |
| DELETE | `/api/jobs/:id` | Cancel/delete document |

Detection parameters: `min_line_width_ratio` (0.16), `max_line_height` (10), `min_rect_area_ratio` (0.001), `max_rect_area_ratio` (0.5). Coordinates are rendered pixels; original page numbers include blank pages. Lines are green and rectangles blue.

See the executable [Bun client](scripts/analyze.ts):

```sh
SKALU_URL=https://skalu.ilmtest.net SKALU_KEY=sk_... bun scripts/analyze.ts document.pdf
```

Generate declarations with `bun run types:generate`: `packages/contracts/dist/types.d.ts`. Exports include API/engine version, filename, detection parameters, pages and DPI. Images use separate URLs instead of base64 JSON.

## Offline engine

```sh
uv run --project packages/engine python packages/engine/skalu.py document.pdf --output results.json --save-viz
```

The original image/folder CLI remains available; hosted processing accepts PDFs only.

## Releases

Release Please tracks root application and `packages/engine/` independently. Conventional commits drive semantic versions. App releases synchronize web/Worker/contracts versions; engine releases update Python metadata and service/CLI markers. `/version` reports app version, Git SHA/build timestamp; exports record the actual engine version. Protocol 1 supports the Worker/container rollout window and must change through a compatible transition. A job detects an engine-version change and fails explicitly rather than exporting mixed-version detections; submit the PDF again after rollout.

Google Cloud deployment/setup is removed. Release Please remains provider-independent release tooling.

Manual GitHub deployment is available in `.github/workflows/deploy.yml`. Configure a scoped `CLOUDFLARE_API_TOKEN` secret and the `CLOUDFLARE_ACCOUNT_ID` repository variable for CI; the local deploy uses your `cf` authentication and the same production domain.
