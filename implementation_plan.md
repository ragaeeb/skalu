# Skalu Migration Plan Update: Bun-First Frontend + Modern Test Stack

## Summary
Revise the previously approved GCP migration to keep all backend/infra goals, but change frontend/tooling standards to:
- Bun package manager + Bun commands (no npm/node scripts in docs/workflows)
- TypeScript style: `type` aliases instead of `interface`
- ES6 arrow functions instead of classic `function` declarations in frontend code
- Frontend tests with `bun:test` (unit + integration) and Playwright E2E (latest)

Pinned baseline (as of **2026-02-18**):
- Bun: `1.3.9`
- Playwright: `1.58.2`

## Important API / Interface Changes
- Backend API contract remains unchanged from the migration plan (`/health`, `/analyze`, `/progress/:id`, `/results/:id`, `/download/:id`).
- Frontend type surface changes:
  - Convert all proposed TS `interface` declarations to `type` aliases.
  - Convert exported classic functions to `const fn = (...) => {}` style.
- Testing interfaces added:
  - `bun:test` suites for component and API integration behavior.
  - Playwright specs for upload/progress/results/download end-to-end flows.

## Implementation Plan Changes

### 1) Frontend scaffolding and package management (Bun-only)
- Create `frontend/` via Bun-compatible Vite workflow.
- Replace all npm commands in migration docs/scripts with Bun equivalents:
  - `bun create vite ...`
  - `bun install`
  - `bun add ...`
  - `bunx shadcn@latest ...`
  - `bun run build`, `bun run test`, etc.
- Commit `bun.lock` and remove npm lockfile assumptions from CI/docs.

### 2) Frontend code style constraints
- In all new TS/TSX files under `frontend/src/`:
  - Use `type` for prop/data contracts (`type DropZoneProps = {...}`).
  - Use arrow functions for utilities, hooks, and components:
    - `export const useJobPolling = (...) => {...}`
    - `export const DropZone = (...) => {...}`
- Keep React 19 + Vite + Tailwind v4 + shadcn/ui stack, but expressed with Bun tooling.

### 3) Unit + integration tests with `bun:test`
- Add frontend test setup:
  - `frontend/tests/unit/**` for pure logic/type-safe API helpers
  - `frontend/tests/integration/**` for component + mocked network behavior
- Use `bun test` and Bun coverage reporting.
- Test scenarios:
  - File upload validation and error handling
  - Polling state transitions (`queued -> processing -> finished/error`)
  - `results?viz=true` vs default payload behavior
  - Download URL generation and result panel rendering
- Coverage policy per your choice:
  - Generate coverage reports, but **no hard fail threshold gate**.

### 4) E2E with Playwright (latest)
- Add Playwright config and tests in `frontend/e2e/` using `@playwright/test@1.58.2`.
- E2E scenarios:
  - Happy path: upload sample file, wait for completion, verify summary/results
  - Error path: unsupported file type
  - Optional viz mode path
  - Download endpoint behavior
- Add local run commands using Bun:
  - `bunx playwright install --with-deps chromium` (CI)
  - `bunx playwright test`

### 5) CI/CD workflow updates for Bun + Playwright
- Update frontend workflow to:
  - Install Bun (GitHub Action for Bun runtime)
  - `bun install --frozen-lockfile`
  - `bun run test` (unit/integration)
  - `bun run build`
  - Playwright browser install + `bunx playwright test`
  - Firebase deploy step unchanged in auth model (`FIREBASE_TOKEN`), but command paths aligned to Bun-managed project.
- Keep Python backend workflows and Terraform workflows as planned (with Python 3.14 update already requested).

### 6) Docs and proposal alignment
- Update `migration_proposal.md`-derived implementation artifacts so they reference Bun commands instead of npm.
- Update `README.md` and `cloud_setup.md`:
  - Bun install prerequisite
  - Bun command examples for dev/test/build
  - Playwright E2E setup and troubleshooting notes

## Test Cases and Scenarios
1. Backend smoke: `/health`, async job lifecycle, viz gating, download response.
2. Frontend unit (`bun:test`): utility and API client logic.
3. Frontend integration (`bun:test`): component behavior with mocked API.
4. Frontend E2E (Playwright): user-level upload-to-results flows.
5. CI verification: Bun install, Bun tests, coverage report generation, Playwright run, frontend build, deploy workflow parse.

## Assumptions and Defaults
- Full migration scope remains enabled (backend + frontend + infra + CI/CD).
- Bun is the only JS package manager/runner in docs and CI.
- Playwright pinned to latest verified (`1.58.2`) at implementation time.
- Coverage expectation is “comprehensive reports and test breadth,” with **no hard numeric gate** (per your selection).
