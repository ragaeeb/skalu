# Repository Guidelines

## Stack Snapshot

- Backend: Flask API (`app.py`) on Python 3.14.
- Frontend: Vite + React + TypeScript in `frontend/` managed with Bun.
- Infra: Terraform in `infra/` for Cloud Run, Artifact Registry, Firebase Hosting, and WIF.
- CI/CD: GitHub Actions in `.github/workflows/`.

## Code and Style

- Prefer using `pathlib.Path` for filesystem paths in tests and new Python code.
- Keep Python style PEP 8 and avoid introducing new lint tools not already configured.
- When adding CLI functionality, expose it through `skalu.py` so the script remains the main entry point.
- For new frontend code, use:
  - Type aliases (`type`) instead of `interface`.
  - ES6 arrow functions instead of classic function declarations.

## Tests

- Keep Python tests in `tests/` and name files `test_*.py`.
- Frontend unit/integration tests live in `frontend/tests/` and run with `bun test`.
- Frontend E2E tests live in `frontend/e2e/` and run with Playwright.

## Common Local Commands

- Start both backend and frontend together:
  - `./dev_up.sh`
- Backend only:
  - `source .venv/bin/activate && python app.py`
- Frontend only:
  - `cd frontend && bun run dev`
- Python tests:
  - `source .venv/bin/activate && pytest -q`
- Frontend tests:
  - `cd frontend && bun run test`
- E2E tests:
  - `cd frontend && bunx playwright test`

## Deployment Notes

- API endpoint includes health check at `GET /health`.
- Results endpoint supports visualization payloads only with `?viz=true`.
- API job state is in-memory; Terraform keeps Cloud Run min instances at 1.
- Configure Terraform backend bucket via init flag:
  - `terraform init -backend-config="bucket=skalu-tfstate-YOUR_PROJECT_ID"`
