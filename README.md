# skalu

Skalu extracts horizontal lines and rectangles from images and PDFs, with a Flask API backend and a React frontend.

## Architecture

- Backend API: Flask (`app.py`) deployed to Google Cloud Run
- Frontend: Vite + React + TypeScript in `frontend/`, deployed to Firebase Hosting
- Infrastructure: Terraform in `infra/`
- CI/CD: GitHub Actions + Workload Identity Federation
- Frontend package manager and scripts: Bun

## Prerequisites

- Python 3.14
- Bun 1.3.9+
- `uv`
- gcloud CLI
- Terraform 1.9+
- Firebase CLI

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
- Start analysis: `POST /analyze` (returns `202` + `job_id`)
- Poll status: `GET /progress/<job_id>`
- Fetch results: `GET /results/<job_id>`
- Include image payloads: `GET /results/<job_id>?viz=true`
- Download JSON: `GET /download/<job_id>`

## Deploy setup (GCP)

1. Configure GCP project + billing.
2. Create Terraform state bucket.
3. Initialize Terraform backend with bucket:
   - `terraform init -backend-config="bucket=skalu-tfstate-YOUR_PROJECT_ID"`
4. Apply Terraform in `infra/`.
5. Add GitHub secrets:
   - `GCP_PROJECT_ID`
   - `GCP_WORKLOAD_IDENTITY_PROVIDER`
   - `GCP_SERVICE_ACCOUNT`
   - `VITE_API_URL`
   - `FIREBASE_TOKEN`
6. Push to `main`.

Detailed setup is in [`cloud_setup.md`](cloud_setup.md).

## CI workflows

- `.github/workflows/test.yml`: Python tests (uv + Python 3.14)
- `.github/workflows/release.yml`: semantic release
- `.github/workflows/deploy-api.yml`: Docker build/push + Cloud Run deploy
- `.github/workflows/deploy-frontend.yml`: Bun tests, Playwright, Firebase deploy
