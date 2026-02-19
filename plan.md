## Implement Single-Shot Cloud Run Architecture with In-Request Streaming Progress

### Summary
Refactor the app from session/job-based orchestration to a stateless single-shot model:
- one `POST /analyze` request does all work,
- optional NDJSON streaming for page-by-page progress in the same request,
- remove persisted job/session endpoints,
- split backend into modules,
- add explicit backend/frontend version endpoints and display in UI,
- keep CI/CD simple for one-shot Cloud Run + Firebase deployment.

### Public API / Interface Changes
1. Keep:
- `GET /health`
- `GET /version` (new)

2. Replace analysis flow:
- `POST /analyze` (single endpoint; multipart form)
  - fields: `file`, detection params, `include_empty_pages`, `include_visualizations`, `stream`
  - `stream=false`: standard JSON result
  - `stream=true`: `application/x-ndjson` with progress events then terminal `result` or `error`

3. Remove:
- `POST /process/<job_id>`
- `GET /progress/<job_id>`
- `GET /events/<job_id>`
- `GET /results/<job_id>`
- `GET /download/<job_id>`

### Implementation Plan (Decision-Complete)

1. Backend modularization
- Create:
  - `backend/app_factory.py`
  - `backend/config.py`
  - `backend/routes/{health.py,version.py,analyze.py}`
  - `backend/services/{analysis.py,streaming.py}`
  - `backend/models.py`
  - `backend/errors.py`
- Keep root `app.py` as thin entrypoint that imports `create_app()`.

2. Single-shot analysis service
- Move processing logic from `app.py` job-thread flow into `backend/services/analysis.py`.
- Input: request-scoped options + uploaded file path.
- Output: final payload with `summary`, `result_data`, `detection_params`, optional `visualizations` and `debug_groups`.
- No global `_jobs`, no session IDs, no cross-request state.

3. Streaming progress protocol (NDJSON)
- Implement generator in `backend/services/streaming.py` using request-local queue + worker thread.
- Event schema:
  - `{"type":"accepted","filename":"...","started_at":"..."}`
  - `{"type":"progress","processed":n,"total":m,"message":"..."}`
  - `{"type":"heartbeat","ts":"..."}`
  - `{"type":"result","payload":{...}}` terminal success
  - `{"type":"error","code":"timeout|processing_error|bad_input","message":"..."}` terminal failure
- Heartbeat interval default: `15s`.
- Ensure streamed response headers:
  - `Content-Type: application/x-ndjson`
  - `Cache-Control: no-cache`
  - `X-Accel-Buffering: no`

4. Timeout and failure behavior
- Add `ANALYZE_TIMEOUT_SECONDS` config (default `3300`).
- Enforce hard timeout in worker path; emit timeout error event or JSON error.
- If request drops, cancel processing best-effort and cleanup temp files.

5. Frontend migration to single-shot stream
- Replace polling/eventsource job model with request-stream model:
  - Add `analyzeFileStream()` in `frontend/src/lib/api.ts` using `fetch` stream reader.
  - Parse NDJSON incrementally; callback on progress/result/error.
- Update `frontend/src/App.tsx`:
  - keep upload + options UI,
  - Process triggers one request,
  - show live page progress from stream,
  - render result when terminal result event arrives.
- Remove dead job/session artifacts:
  - `frontend/src/hooks/useJobPolling.ts` (delete or replace with stream hook),
  - all code dependent on job IDs/results endpoints.

6. Versioning
- Add backend version source in `pyproject.toml` (`project.version`).
- Add `GET /version` response:
  - `backend_version`, `frontend_version` (if passed), `git_sha`, `build_time`.
- Frontend build-time version injection from `frontend/package.json` via Vite define.
- Display both versions in frontend footer/status area.

7. Config / DX
- Add root `.env.example` with:
  - `PORT`, `ALLOWED_ORIGINS`, `MAX_CONTENT_LENGTH`,
  - `ANALYZE_TIMEOUT_SECONDS`, `STREAM_HEARTBEAT_SECONDS`,
  - `APP_VERSION`, `GIT_SHA`, `LOG_LEVEL`.
- Update README commands and API docs to single-shot flow.

8. Infra + CI/CD alignment (Cloud Run)
- Terraform (`infra/main.tf`):
  - `min_instance_count = 0`
  - container concurrency = `1`
  - timeout aligned with `ANALYZE_TIMEOUT_SECONDS` (<= 3600)
- GitHub deploy workflow:
  - set env vars on deploy (`APP_VERSION`, `GIT_SHA`, timeout-related vars),
  - post-deploy smoke checks for `/health` and `/version`.
- Keep Trigger.dev integration out of runtime; add `docs/triggerdev-future.md` only.

### Test Cases and Scenarios
1. Backend unit/integration
- `POST /analyze` non-stream success (PDF/image).
- `POST /analyze` stream event ordering and terminal result.
- Timeout path returns terminal `error`.
- Invalid params/file types return 4xx with stable error schema.
- Visualizations included only when requested.

2. Frontend
- NDJSON parser handles chunk splits and malformed line tolerance.
- Process button lifecycle: idle -> running -> result/error.
- Live progress updates per page.
- Version display includes frontend build version and backend `/version`.

3. E2E
- happy path (single-shot stream),
- timeout/error path,
- large PDF rendering remains performant with virtualization.

### Assumptions and Defaults
1. No durability/no sessions/no resumable jobs.
2. Trigger.dev deferred; only documented as future option.
3. Hard timeout strategy is intentional (no async fallback).
4. Streamed progress is in-request NDJSON, not SSE/websocket.
5. Backend and frontend versions are independently managed and displayed.
