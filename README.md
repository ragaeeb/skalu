# skalu

Skalu extracts horizontal lines and rectangles from images and PDFs, with a Flask API backend and a React frontend.

## Architecture

- Backend API: Flask (`app.py`) deployed to Google Cloud Run
- Frontend: Vite + React + TypeScript in `frontend/`, built into the Cloud Run container
- Infrastructure: Terraform in `infra/`
- CI: GitHub Actions (tests + releases)
- CD: Cloud Build GitHub triggers (direct deploy on push)
- Frontend package manager and scripts: Bun

## Prerequisites

- Python 3.14
- Bun 1.3.9+
- `uv`
- gcloud CLI
- Terraform 1.9+

## Local development

### One-command startup

```bash
./dev_up.sh
```

This launches:
- Backend on `http://localhost:8080`
- Frontend on `http://localhost:5173`

The script traps kill signals and shuts both processes down together.

### Backend only

```bash
uv venv --python 3.14 .venv
source .venv/bin/activate
uv pip install -r requirements_dev.txt
python app.py
```

### Frontend only

```bash
cd frontend
cp .env.example .env.local
bun install
bun run dev
```

Frontend proxies API routes to `http://localhost:8080` in dev mode.

### Environment

Copy `.env.example` and adjust values as needed:

```bash
cp .env.example .env
```

Main backend variables:
- `PORT`
- `ALLOWED_ORIGINS`
- `MAX_CONTENT_LENGTH`
- `ANALYZE_TIMEOUT_SECONDS`
- `STREAM_HEARTBEAT_SECONDS`
- `APP_VERSION`
- `GIT_SHA`
- `BUILD_TIME`
- `LOG_LEVEL`

## Testing

### Backend tests

```bash
source .venv/bin/activate
pytest -q
```

### Frontend unit + integration (`bun:test`)

```bash
cd frontend
bun run test
```

### Frontend E2E (Playwright)

```bash
cd frontend
bunx playwright install chromium
bunx playwright test
```

## API highlights

- Health check: `GET /health`
- Version metadata: `GET /version`
- Analyze file: `POST /analyze` (multipart)
  - Fields:
    - `file`
    - `include_empty_pages` (`true|false`)
    - `include_visualizations` (`true|false`)
    - `stream` (`true|false`)
    - `min_line_width_ratio`
    - `max_line_height`
    - `min_rect_area_ratio`
    - `max_rect_area_ratio`
  - `stream=false`: returns JSON payload
  - `stream=true`: returns `application/x-ndjson` events (`accepted`, `progress`, `heartbeat`, `result`, `error`)

## Deploy setup (GCP)

1. Configure GCP project + billing.
2. Create Terraform state bucket.
3. Initialize Terraform backend with bucket:
   - `terraform init -backend-config="bucket=skalu-tfstate-YOUR_PROJECT_ID"`
4. Apply Terraform in `infra/`.
5. Connect GitHub repository to Cloud Build (one-time in GCP console).
6. Push to `main`.

Detailed setup is in [`cloud_setup.md`](cloud_setup.md).

## CI workflows

- `.github/workflows/test.yml`: Python tests (uv + Python 3.14)
- `.github/workflows/release.yml`: Release Please (manifest mode for backend + frontend)

## Cloud Build pipelines

- `cloudbuild/api.cloudbuild.yaml`: frontend tests + full image build (frontend + backend) + Cloud Run deploy + smoke checks

## Versioning

Release Please reads conventional commits on `main` and opens release PRs:

- `fix:` -> patch bump
- `feat:` -> minor bump
- `feat!:` or `BREAKING CHANGE:` -> major bump

Version sources:

- Backend: `pyproject.toml` (`project.version`)
- Frontend: `frontend/package.json` (`version`)
