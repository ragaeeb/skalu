# Repository Guidelines

This file is the contributor quick reference.  
For full architecture details, read `docs/architecture.md`.

## Stack Snapshot

- Backend: Flask API on Python 3.14 (`app.py` -> `backend/app_factory.py`).
- Frontend: Vite + React + TypeScript in `frontend/`, managed with Bun.
- Processing core: `skalu.py` + `demo_utils.py` (OpenCV + PyMuPDF + Pillow).
- Infra: Terraform in `infra/` (Cloud Run, Artifact Registry, Cloud Build trigger + IAM).
- Deploy pipeline: Cloud Build trigger on push to `main`, config in `cloudbuild/api.cloudbuild.yaml`.
- Release/versioning: Release Please manifest mode + separate workflow for API type declarations.

## Documentation Sources

- Architecture and runtime/deploy flow: `docs/architecture.md`.
- Setup/bootstrap/deploy troubleshooting: `cloud_setup.md`.
- Public API and usage examples: `README.md`.

## Repository Structure

- `app.py`: thin runtime entrypoint.
- `backend/`:
  - `routes/`: `analyze`, `health`, `version`, `frontend`.
  - `services/`: analysis + NDJSON streaming orchestration.
  - `models.py`: request option parsing/validation.
  - `config.py`: env-driven settings and version metadata.
- `frontend/`:
  - `src/`: app UI + API client + shared types + payload schemas.
  - `tests/`: Bun unit/integration tests.
  - `e2e/`: Playwright tests.
  - `dist-types/`: generated API declaration output (`skalu-api.d.ts`).
- `tests/`: backend pytest suite.
- `infra/`: Terraform resources for runtime + CI/CD plumbing.
- `.github/workflows/`: test/release workflows.

## API Contract Notes

- Health: `GET /health`.
- Version: `GET /version`.
- Analyze: `POST /analyze` with multipart fields:
  - One of: `file` or `file_url` (public `http(s)` PDF URL).
  - Flags: `include_empty_pages`, `include_visualizations`, `stream`.
  - Detection params:
    - `min_line_width_ratio`
    - `max_line_height`
    - `min_rect_area_ratio`
    - `max_rect_area_ratio`
- Analyze response payload shape:
  - `detection_params` (top-level, input params actually used)
  - `result_data` (typed union: PDF shape or image shape)
  - `processed_filename`
  - `visualizations`
  - `debug_groups`

## Frontend Conventions

- Use `type` aliases, not `interface`.
- Prefer arrow functions over `function` declarations.
- Use `[]` array type style (for example `Foo[]`, not `Array<Foo>`).
- Keep API response typing aligned with `frontend/src/types.ts`.
- Contract runtime schema lives in `frontend/src/schemas/analyzePayload.ts` (Valibot).
- Declaration generation command:
  - `cd frontend && bun run types:generate`
  - Output: `frontend/dist-types/skalu-api.d.ts`

## Backend Conventions

- Prefer `pathlib.Path` in tests and new Python code.
- Keep new code PEP 8-friendly and avoid introducing additional lint stacks.
- Add CLI-facing logic through `skalu.py` (project entrypoint for processing).
- Keep `/analyze` stateless and request-scoped (temp workspace cleanup is required).

## Testing Conventions

- Backend tests:
  - Location: `tests/`
  - Naming: `test_*.py`
  - Run: `source .venv/bin/activate && pytest -q`
- Frontend tests:
  - Unit/integration location: `frontend/tests/`
  - Framework: `bun:test`
  - Test names should follow `it('should ...')`
  - Run: `cd frontend && bun test`
- Frontend E2E:
  - Location: `frontend/e2e/`
  - Run with Playwright only:
    - `cd frontend && bunx playwright test`

## Local Development

- Start both services:
  - `./dev_up.sh`
- Backend only:
  - `source .venv/bin/activate && python app.py`
- Frontend only:
  - `cd frontend && bun run dev`

## CI/CD and Release Workflows

- `.github/workflows/test.yml`:
  - Backend pytest + frontend Bun tests + Codecov upload.
- `.github/workflows/release.yml`:
  - Release Please (manifest mode, backend/frontend components).
- `.github/workflows/release-types.yml`:
  - On published releases, generates and uploads `skalu-api.d.ts` asset.
- `cloudbuild/api.cloudbuild.yaml`:
  - Frontend tests, image build/push, Cloud Run deploy, smoke checks.

## Versioning Notes

- Release Please uses conventional commits:
  - `fix:` patch
  - `feat:` minor
  - `feat!:` or `BREAKING CHANGE:` major
- Backend version source: `pyproject.toml`.
- Frontend version source: `frontend/package.json`.
- Backend deploy env sets `APP_VERSION`, `GIT_SHA`, `BUILD_TIME` for `/version`.

## Deployment Notes

- Frontend is bundled into the same Cloud Run container as backend.
- Cloud Run min instances are configured to `0`.
- Terraform backend bucket config example:
  - `terraform init -backend-config="bucket=skalu-tfstate-YOUR_PROJECT_ID"`
