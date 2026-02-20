# skalu

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![codecov](https://codecov.io/gh/ragaeeb/skalu/graph/badge.svg?token=VBJH3TR0KZ)](https://codecov.io/gh/ragaeeb/skalu)
[![Flask](https://img.shields.io/badge/Flask-3.1.2-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Bun](https://img.shields.io/badge/Bun-1.3.9+-fbf0df?logo=bun&logoColor=111111)](https://bun.sh/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111111)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)](https://vite.dev/)
[![Terraform](https://img.shields.io/badge/Terraform-Infra-844FBA?logo=terraform&logoColor=white)](https://www.terraform.io/)
[![wakatime](https://wakatime.com/badge/user/a0b906ce-b8e7-4463-8bce-383238df6d4b/project/26c7c021-8f40-4bb9-aa97-ba8965462f2d.svg)](https://wakatime.com/badge/user/a0b906ce-b8e7-4463-8bce-383238df6d4b/project/26c7c021-8f40-4bb9-aa97-ba8965462f2d)
[![Google Cloud Run](https://img.shields.io/badge/Google_Cloud_Run-Serverless-4285F4?logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Tests](https://github.com/ragaeeb/skalu/actions/workflows/test.yml/badge.svg)](https://github.com/ragaeeb/skalu/actions/workflows/test.yml)
[![Release Please](https://github.com/ragaeeb/skalu/actions/workflows/release.yml/badge.svg)](https://github.com/ragaeeb/skalu/actions/workflows/release.yml)
[![Release API Types](https://github.com/ragaeeb/skalu/actions/workflows/release-types.yml/badge.svg)](https://github.com/ragaeeb/skalu/actions/workflows/release-types.yml)
[![codecov](https://codecov.io/gh/ragaeeb/skalu/branch/main/graph/badge.svg)](https://codecov.io/gh/ragaeeb/skalu)

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

## Type declarations

Generate a client-consumable API declaration file:

```bash
cd frontend
bun run types:generate
```

Output file:
- `frontend/dist-types/skalu-api.d.ts`

Release automation:
- On each published GitHub Release, `.github/workflows/release-types.yml` generates and uploads `skalu-api.d.ts` as a release asset.

Client usage (Vite or Next.js):
1. Download `skalu-api.d.ts` from the release assets.
2. Add it to your app, for example `src/types/skalu-api.d.ts`.
3. Import the types in your API client code.

Example:

```ts
import type { AnalyzePayload, AnalyzeStreamEvent } from "./types/skalu-api";

export const parseAnalyzeResponse = async (res: Response): Promise<AnalyzePayload> => {
  return res.json() as Promise<AnalyzePayload>;
};

export const parseStreamEvent = (line: string): AnalyzeStreamEvent => {
  return JSON.parse(line) as AnalyzeStreamEvent;
};
```

TypeScript config note:
- Ensure your `tsconfig.json` includes your declaration location (for example `src/**/*` or `src/types/**/*`).

## API highlights

- Health check: `GET /health`
- Version metadata: `GET /version`
- Analyze file: `POST /analyze` (multipart)
  - Fields:
    - `file` (mutually exclusive with `file_url`)
    - `file_url` (mutually exclusive with `file`; public `http(s)` PDF URL)
    - `include_empty_pages` (`true|false`)
    - `include_visualizations` (`true|false`)
    - `stream` (`true|false`)
    - `min_line_width_ratio`
    - `max_line_height`
    - `min_rect_area_ratio`
    - `max_rect_area_ratio`
  - `stream=false`: returns JSON payload
  - `stream=true`: returns `application/x-ndjson` events (`accepted`, `progress`, `heartbeat`, `result`, `error`)

## Public API reference

Base URL:
- `https://skalu-api-<service-hash>-uc.a.run.app`

### `GET /health`

Purpose:
- Liveness/readiness check.

Response `200`:

```json
{ "status": "ok" }
```

### `GET /version`

Purpose:
- Returns backend version/build metadata.

Response `200`:

```json
{
  "backend_version": "0.2.0",
  "frontend_version": null,
  "git_sha": "dev",
  "build_time": "unknown"
}
```

### `POST /analyze`

Purpose:
- Analyze one uploaded PDF/image in a single request.

Request:
- Content type: `multipart/form-data`
- Fields:
  - `file` (optional): uploaded PDF or image (`pdf,png,jpg,jpeg,bmp,tiff,webp`)
  - `file_url` (optional): public PDF URL (only `http`/`https`)
  - `include_empty_pages` (optional, default `true`)
  - `include_visualizations` (optional, default `false`)
  - `stream` (optional, default `false`)
  - `min_line_width_ratio` (optional, default `0.2`)
  - `max_line_height` (optional, default `10`)
  - `min_rect_area_ratio` (optional, default `0.001`)
  - `max_rect_area_ratio` (optional, default `0.5`)

Success (`stream=false`, `200`):
- JSON object containing:
  - `result_data`
  - `summary`
  - `detection_params`
  - optional `visualizations`, `debug_groups`

Success (`stream=true`, `200`):
- `Content-Type: application/x-ndjson`
- Event types:
  - `accepted`
  - `progress`
  - `heartbeat`
  - `result` (terminal success)
  - `error` (terminal failure)

Common errors:
- `400`: missing file, unsupported extension, invalid params
- `400`: invalid `file_url` (non-public host, bad scheme, non-PDF response, too large)
- `408`: analysis timeout
- `500`: processing/storage failure

### `file_url` security checks

When `file_url` is provided, the API enforces sanity checks before processing:
- URL must be `http://` or `https://`.
- Host must resolve to public IPs only (blocks loopback/private/link-local/reserved ranges).
- `localhost` and metadata hosts are blocked.
- Response must look like a PDF (`Content-Type` check) and download size is capped by server `MAX_CONTENT_LENGTH`.
- `file` and `file_url` cannot be sent together.

## Deploy setup (GCP)

1. Authenticate and select project:
   - `gcloud auth login`
   - `gcloud auth application-default login`
   - `gcloud config set project YOUR_PROJECT_ID`
   - `gcloud auth application-default set-quota-project YOUR_PROJECT_ID`
2. Link billing to the project.
3. Run bootstrap:
   - `scripts/bootstrap_cloud.sh --region us-central1 --allowed-origins "*" --run-terraform-apply`
4. Complete one-time Cloud Build GitHub connection in console:
   - `https://console.cloud.google.com/cloud-build/triggers;region=global/connect?project=YOUR_PROJECT_ID`
5. Re-run:
   - `terraform -chdir=infra apply`
6. Verify:
   - `API_URL="$(terraform -chdir=infra output -raw api_url)"`
   - `curl -fsS "${API_URL}/health"`
   - `curl -fsS "${API_URL}/version"`
7. Push to `main` to trigger deploys via Cloud Build.
   - Note: trigger runs when changed files match configured deploy paths (`backend/**`, `frontend/**`, `Dockerfile`, etc.).

Detailed setup is in [`cloud_setup.md`](cloud_setup.md).

## Monitoring and logs

### Local development logs

- Combined local logs (backend + frontend):

```bash
./dev_up.sh
```

- Backend only logs:

```bash
source .venv/bin/activate
python app.py
```

- Frontend only logs:

```bash
cd frontend
bun run dev
```

### Cloud Build deploy logs

- List recent builds:

```bash
gcloud builds list --project YOUR_PROJECT_ID --region us-central1 --limit=20
```

- Stream a build:

```bash
gcloud builds log --project YOUR_PROJECT_ID --region us-central1 --stream BUILD_ID
```

- Console:
  - Cloud Build -> History

### Cloud Run service/revision logs (API + frontend container)

- Tail service logs:

```bash
gcloud run services logs tail skalu-api --project YOUR_PROJECT_ID --region us-central1
```

- Read recent logs:

```bash
gcloud run services logs read skalu-api --project YOUR_PROJECT_ID --region us-central1 --limit=200
```

- Read logs for one specific revision:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="skalu-api" AND resource.labels.revision_name="REVISION_NAME"' \
  --project YOUR_PROJECT_ID \
  --limit=200
```

- Console:
  - Cloud Run -> `skalu-api` -> Logs
  - Cloud Logging -> Logs Explorer (filter `resource.type="cloud_run_revision"`)

## Deployed URL shape

- Terraform output `api_url` is your base URL.
- Example format (Cloud Run):
  - `https://skalu-api-<service-hash>-uc.a.run.app`
- Example endpoints:
  - `https://skalu-api-<service-hash>-uc.a.run.app/health`
  - `https://skalu-api-<service-hash>-uc.a.run.app/version`
  - `https://skalu-api-<service-hash>-uc.a.run.app/analyze`

## Calling the API from another app (TypeScript)

### Non-stream request (`stream=false`)

```ts
const analyzeFile = async (baseUrl: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  form.append("include_empty_pages", "true");
  form.append("include_visualizations", "false");
  form.append("stream", "false");
  form.append("min_line_width_ratio", "0.2");
  form.append("max_line_height", "10");
  form.append("min_rect_area_ratio", "0.001");
  form.append("max_rect_area_ratio", "0.5");

  const res = await fetch(`${baseUrl}/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(`Analyze failed: ${res.status} ${await res.text()}`);
  }

  return await res.json();
};
```

### URL-based request (`file_url`)

```ts
const analyzePdfUrl = async (baseUrl: string, pdfUrl: string) => {
  const form = new FormData();
  form.append("file_url", pdfUrl);
  form.append("include_empty_pages", "true");
  form.append("include_visualizations", "false");
  form.append("stream", "false");

  const res = await fetch(`${baseUrl}/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(`Analyze failed: ${res.status} ${await res.text()}`);
  }

  return await res.json();
};
```

### Streaming request (`stream=true`, NDJSON)

```ts
type StreamEvent =
  | { type: "accepted"; filename: string; started_at: string }
  | { type: "progress"; processed: number; total: number; message: string }
  | { type: "heartbeat"; ts: string }
  | { type: "result"; payload: unknown }
  | { type: "error"; code: string; message: string };

const analyzeFileStream = async (
  baseUrl: string,
  file: File,
  onEvent: (event: StreamEvent) => void,
) => {
  const form = new FormData();
  form.append("file", file);
  form.append("include_empty_pages", "true");
  form.append("include_visualizations", "false");
  form.append("stream", "true");

  const res = await fetch(`${baseUrl}/analyze`, {
    method: "POST",
    body: form,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Stream request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex !== -1) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (line.length > 0) {
        onEvent(JSON.parse(line) as StreamEvent);
      }
      newlineIndex = buffer.indexOf("\n");
    }
  }
};
```

## External access and CORS

- Yes, another app can call this API from outside your project.
- Server-to-server calls are not blocked by CORS.
- Browser calls are subject to CORS:
  - `ALLOWED_ORIGINS="*"` allows any browser origin.
  - If you lock down `ALLOWED_ORIGINS`, only listed origins can call from browsers.

## CI workflows

- `.github/workflows/test.yml`: Python tests (uv + Python 3.14)
- `.github/workflows/release.yml`: Release Please (manifest mode for backend + frontend)
- `.github/workflows/release-types.yml`: Generates `skalu-api.d.ts` and uploads it to published GitHub Releases

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
