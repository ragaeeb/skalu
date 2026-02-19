# Skalu — Migration Proposal: React + Flask on Google Cloud Run

> **Audience:** AI coding agent  
> **Goal:** Migrate Skalu from a monolithic Flask + Jinja/Streamlit app to a split architecture: a Vite + React 19 + Tailwind v4 + shadcn/ui frontend deployed to Firebase Hosting, and a cleaned-up Flask API backend deployed to Google Cloud Run. All infrastructure is managed via Terraform. CI/CD runs on GitHub Actions with keyless auth via Workload Identity Federation.

---

## 0. Summary of Changes

| Area | Action |
|---|---|
| `streamlit_app.py` | **DELETE** — replaced by React frontend |
| `skalu.py` (Streamlit devcontainer) | Remove Streamlit from `devcontainer.json` |
| `render.yaml` | **DELETE** — no longer deploying to Render |
| `templates/index.html` | **DELETE** — replaced by React app |
| `requirements.txt` | Remove `streamlit`, `gunicorn` moves to `requirements.txt` from implicit; add `flask-cors`, `flask-compress`, `flask-limiter` |
| `app.py` | Strip template rendering, add CORS, compression, rate limiting, health endpoint, structured logging |
| `Dockerfile` | Update for pure API server, Python 3.13, no static file serving |
| `docker-compose.yml` | Update for local dev with CORS env var |
| `frontend/` | **CREATE** — new Vite + React 19 + Tailwind v4 + shadcn/ui app |
| `infra/` | **CREATE** — Terraform for Cloud Run, Firebase Hosting, Workload Identity Federation, Artifact Registry |
| `.github/workflows/` | Replace `release.yml`; update `test.yml`; add `deploy-api.yml`, `deploy-frontend.yml` |

---

## 1. Files to Delete

Remove these files entirely from the repository:

```
streamlit_app.py
render.yaml
templates/index.html         (delete templates/ directory entirely)
```

Remove the `templates/` directory from `.gitignore` if it is listed there.

---

## 2. Backend Changes

### 2.1 `requirements.txt`

Replace the entire file with:

```txt
# Runtime dependencies
opencv-python-headless>=4.12.0.88
numpy>=2.2.5
tqdm>=4.67.1
PyMuPDF>=1.26.6
Pillow>=12.0.0
Flask>=3.1.2
flask-cors>=6.0.2
flask-compress>=1.17
Flask-Limiter>=4.0.0
gunicorn>=25.1.0
```

> Note: Do NOT include `streamlit` — it is removed entirely.

### 2.2 `requirements_dev.txt`

```txt
# Development and testing dependencies
-r requirements.txt

pytest>=9.0.1
pytest-cov>=7.0.0
pytest-mock>=3.15.1
coverage>=7.11.3
```

### 2.3 `app.py` — Full Rewrite

Replace `app.py` entirely with the following. Key changes from the original:
- Remove all `render_template` imports and usage (Jinja templating gone)
- Add `flask-cors` with environment-variable-controlled origins
- Add `flask-compress` for gzip on all JSON responses
- Add `flask-limiter` with in-memory storage (sufficient for single-user personal use)
- Add a `/health` endpoint for Cloud Run health checks
- Add structured JSON logging suitable for Google Cloud Logging
- Strip visualizations and debug groups from the default `/results` response; make them opt-in via query param `?viz=true`
- Remove the `download/<job_id>` endpoint's dependency on workdir files (use in-memory result stored on job dict)

```python
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import uuid
from typing import Dict

from flask import Flask, Response, jsonify, request
from flask_compress import Compress
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename

from demo_utils import (
    ALLOWED_EXTENSIONS,
    DEFAULT_PARAMS,
    allowed_file,
    build_summary,
    collect_debug_groups,
    collect_visualizations,
    encode_image_as_data_url,
    job_progress_message,
)
from skalu import process_pdf, process_single_image

# ---------------------------------------------------------------------------
# Structured logging for Google Cloud Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s"}',
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "skalu-demo-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)  # 10 MB default
)

# CORS — allow the frontend origin only. Set ALLOWED_ORIGINS env var in production.
# Example: ALLOWED_ORIGINS=https://skalu.web.app,https://skalu.firebaseapp.com
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else "*"
CORS(app, origins=_origins, supports_credentials=False)

# Gzip compression for all JSON responses
Compress(app)

# Rate limiting — in-memory is fine for personal single-user use
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "30 per hour"],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------
_jobs: Dict[str, Dict] = {}
_jobs_lock = threading.Lock()


def _process_job(job_id: str, suffix: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return

    workdir = job["workdir"]
    filename = job["filename"]
    input_path = os.path.join(workdir, filename)
    output_json_path = os.path.join(workdir, "results.json")
    debug_dir = os.path.join(workdir, "debug")

    def progress_callback(done: int, total: int) -> None:
        with job["lock"]:
            job["processed"] = done
            job["total"] = total
            job["status"] = "processing"
            job["message"] = job_progress_message(done, total, suffix)

    try:
        with job["lock"]:
            job["status"] = "processing"
            job["message"] = "Starting analysis"

        logger.info("Starting job %s for file %s", job_id, filename)

        if suffix == ".pdf":
            success = process_pdf(
                input_path,
                output_json_path,
                params=DEFAULT_PARAMS,
                debug_dir=debug_dir,
                save_visualization=True,
                progress_callback=progress_callback,
            )
        else:
            success = process_single_image(
                input_path,
                output_json_path,
                params=DEFAULT_PARAMS,
                debug_dir=debug_dir,
                save_visualization=True,
                progress_callback=progress_callback,
            )

        if not success:
            raise RuntimeError("Processing failed — please try another file.")

        with open(output_json_path, "r", encoding="utf-8") as fh:
            result_data = json.load(fh)

        result_json = json.dumps(result_data, indent=4, ensure_ascii=False)
        summary = build_summary(result_data)

        # Collect visualizations and debug groups while workdir still exists
        debug_groups = []
        for group in collect_debug_groups(debug_dir):
            images = []
            for image in group["images"]:
                data_url = encode_image_as_data_url(image["path"])
                if data_url:
                    images.append({"name": image["name"], "data_url": data_url})
            if images:
                debug_groups.append({"title": group["title"], "images": images})

        visualizations = []
        for viz in collect_visualizations(workdir):
            data_url = encode_image_as_data_url(viz["path"])
            if data_url:
                visualizations.append({"label": viz["label"], "data_url": data_url})

        download_filename = f"{os.path.splitext(filename)[0]}_results.json"
        detection_params = result_data.get("detection_params")

        payload = {
            "result_json": result_json,
            "result_data": result_data,
            "summary": summary,
            "processed_filename": filename,
            "detection_params": detection_params,
            # Visualizations are stored but only returned when ?viz=true is set
            "_visualizations": visualizations,
            "_debug_groups": debug_groups,
            "download_filename": download_filename,
        }

        with job["lock"]:
            job["status"] = "finished"
            job["processed"] = job.get("total", 0) or job.get("processed", 0)
            job["message"] = "Processing complete"
            job["result"] = payload

        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Job %s failed: %s", job_id, exc)
        with job["lock"]:
            job["status"] = "error"
            job["error"] = str(exc)
            job["message"] = f"Failed: {exc}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        with job["lock"]:
            job["workdir"] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
@limiter.exempt
def health():
    """Cloud Run health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    uploaded_file = request.files.get("file")
    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"error": "Please choose a PDF or image file to analyze."}), 400

    filename = secure_filename(uploaded_file.filename)
    if not allowed_file(filename):
        return jsonify({"error": "Unsupported file type."}), 400

    suffix = os.path.splitext(filename)[1].lower()

    try:
        workdir = tempfile.mkdtemp(prefix="skalu_job_")
    except Exception as exc:
        logger.exception("Failed to allocate workspace")
        return jsonify({"error": f"Unable to prepare workspace: {exc}"}), 500

    input_path = os.path.join(workdir, filename)
    try:
        uploaded_file.save(input_path)
    except Exception as exc:
        logger.exception("Failed to save upload")
        shutil.rmtree(workdir, ignore_errors=True)
        return jsonify({"error": f"Unable to save uploaded file: {exc}"}), 500

    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "filename": filename,
        "status": "queued",
        "processed": 0,
        "total": 0,
        "message": "Queued",
        "error": None,
        "result": None,
        "workdir": workdir,
        "lock": threading.Lock(),
    }

    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_process_job, args=(job_id, suffix), daemon=True)
    thread.start()
    logger.info("Queued job %s for file %s", job_id, filename)

    return jsonify({"job_id": job_id}), 202


@app.route("/progress/<job_id>", methods=["GET"])
def progress(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    with job["lock"]:
        response = {
            "status": job["status"],
            "processed": job.get("processed", 0),
            "total": job.get("total", 0),
            "message": job.get("message"),
            "filename": job.get("filename"),
            "result_ready": job.get("status") == "finished",
        }
        if job["status"] == "error":
            response["error"] = job.get("error")
    return jsonify(response)


@app.route("/results/<job_id>", methods=["GET"])
def results(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    with job["lock"]:
        if job["status"] != "finished" or not job.get("result"):
            if job["status"] == "error":
                return jsonify({"error": job.get("error", "Processing failed")}), 400
            return jsonify({"error": "Results not ready"}), 202

        result = job["result"]

    # Only include heavy image payloads when explicitly requested (?viz=true)
    include_viz = request.args.get("viz", "false").lower() == "true"

    payload = {
        "result_json": result["result_json"],
        "result_data": result["result_data"],
        "summary": result["summary"],
        "processed_filename": result["processed_filename"],
        "detection_params": result["detection_params"],
        "download_filename": result["download_filename"],
        "visualizations": result["_visualizations"] if include_viz else [],
        "debug_groups": result["_debug_groups"] if include_viz else [],
    }
    return jsonify(payload)


@app.route("/download/<job_id>", methods=["GET"])
def download(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    with job["lock"]:
        if job["status"] != "finished" or not job.get("result"):
            if job["status"] == "error":
                return jsonify({"error": job.get("error", "Processing failed")}), 400
            return jsonify({"error": "Results not ready"}), 202
        result_json = job["result"].get("result_json")
        download_filename = job["result"].get("download_filename") or "results.json"

    return Response(
        result_json or "{}",
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={download_filename}"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
```

### 2.4 `demo_utils.py`

No structural changes required. However, update `encode_image_as_data_url` to resize images before base64-encoding to reduce egress payload size:

```python
# In demo_utils.py, replace encode_image_as_data_url with:
def encode_image_as_data_url(path: str, max_width: int = 900) -> Optional[str]:
    """Load an image, resize to max_width, and return as a data URL."""
    try:
        from PIL import Image as PILImage
        import io as _io
        with PILImage.open(path) as img:
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), PILImage.LANCZOS)
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=65, optimize=True)
            encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    except OSError:
        return None
    return f"data:image/jpeg;base64,{encoded}"
```

### 2.5 `Dockerfile`

Replace the existing Dockerfile entirely. Key changes: Python 3.13 slim, `gunicorn` with `--no-cpu-throttling`-friendly config, no static file serving, proper `PORT` env var usage, non-root user for security:

```dockerfile
FROM python:3.13-slim

# Install system dependencies for OpenCV and PyMuPDF
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libgl1 \
        libglib2.0-0 \
        libfreetype6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy dependency manifests first (cache layer)
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY app.py demo_utils.py skalu.py ./

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Cloud Run injects PORT; default to 8080
ENV PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# Single worker — e2-micro has 1 vCPU; threading handles concurrency
CMD ["sh", "-c", "gunicorn --workers 1 --threads 8 --timeout 3600 --bind 0.0.0.0:${PORT} app:app"]
```

### 2.6 `docker-compose.yml`

Update for local development. The frontend proxy handles CORS in production but for local dev you can set `ALLOWED_ORIGINS=*`:

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - ALLOWED_ORIGINS=http://localhost:5173
      - MAX_CONTENT_LENGTH=10485760
    volumes:
      - /tmp/skalu-jobs:/tmp
```

### 2.7 `entrypoint.sh`

Remove the `start_web` / Streamlit logic. Simplify to CLI-only since the container now starts via `CMD` in the Dockerfile for the web service:

```bash
#!/bin/bash
set -e

process_directory() {
    local input_dir=$1
    local output_json="${OUTPUT_DIR:-/output}/structures.json"
    echo "Processing all images in ${input_dir}"
    python /app/skalu.py "${input_dir}" --output "${output_json}"
}

process_single() {
    local file_path=$1
    local base_name
    base_name=$(basename "${file_path}" | cut -f1 -d'.')
    local output_json="${OUTPUT_DIR:-/output}/${base_name}_structures.json"
    echo "Processing ${file_path}"
    python /app/skalu.py "${file_path}" --output "${output_json}"
}

case "$1" in
    all|'')
        process_directory "${INPUT_DIR:-/data}"
        ;;
    *)
        if [ -f "$1" ]; then
            process_single "$1"
        elif [ -d "$1" ]; then
            process_directory "$1"
        else
            echo "Error: $1 is not a valid file or directory."
            exit 1
        fi
        ;;
esac

chmod -R 777 "${OUTPUT_DIR:-/output}" 2>/dev/null || true
echo "Done."
```

### 2.8 `devcontainer.json`

Remove all Streamlit references. Update to just install Python deps for backend development:

```json
{
  "name": "Skalu API",
  "image": "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm",
  "customizations": {
    "vscode": {
      "settings": {},
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance"
      ]
    }
  },
  "updateContentCommand": "[ -f packages.txt ] && sudo apt update && sudo xargs apt install -y <packages.txt; pip3 install --user -r requirements_dev.txt; echo '✅ Dependencies installed'",
  "forwardPorts": [8080]
}
```

---

## 3. Frontend — New `frontend/` Directory

Create a new `frontend/` directory at the repo root. This is a standalone Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui application.

### 3.1 Scaffold

The agent should run the following commands to scaffold the project (do not commit `node_modules`):

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install tailwindcss @tailwindcss/vite
npm install @types/node
npx shadcn@latest init   # Choose: new-york style, zinc base color
npx shadcn@latest add button card badge progress separator
```

### 3.2 `frontend/vite.config.ts`

```typescript
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // During local dev, proxy API calls to the Flask backend
      "/analyze": "http://localhost:8080",
      "/progress": "http://localhost:8080",
      "/results": "http://localhost:8080",
      "/download": "http://localhost:8080",
      "/health": "http://localhost:8080",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
})
```

### 3.3 `frontend/tsconfig.json`

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### 3.4 `frontend/tsconfig.app.json`

Add path alias to the existing generated file:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### 3.5 `frontend/src/index.css`

```css
@import "tailwindcss";
```

### 3.6 `frontend/src/types.ts`

```typescript
export type JobStatus = "queued" | "processing" | "finished" | "error"

export interface ProgressResponse {
  status: JobStatus
  processed: number
  total: number
  message: string
  filename: string
  result_ready: boolean
  error?: string
}

export interface DetectionParams {
  min_line_width_ratio: number
  max_line_height: number
  min_rect_area_ratio: number
  max_rect_area_ratio: number
}

export interface SummaryPage {
  page: number
  lines: number
  rectangles: number
  size: [number, number]
}

export interface SummaryItem {
  name: string
  lines: number
  rectangles: number
  dimensions: [number, number]
}

export interface Summary {
  type: "pdf" | "image"
  pages?: SummaryPage[]
  items?: SummaryItem[]
}

export interface ResultsResponse {
  result_json: string
  summary: Summary | null
  processed_filename: string
  detection_params: DetectionParams
  download_filename: string
  visualizations: Array<{ label: string; data_url: string }>
  debug_groups: Array<{
    title: string
    images: Array<{ name: string; data_url: string }>
  }>
}
```

### 3.7 `frontend/src/hooks/useJobPolling.ts`

```typescript
import { useState, useEffect, useRef } from "react"
import type { ProgressResponse } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL ?? ""

export function useJobPolling(jobId: string | null) {
  const [status, setStatus] = useState<ProgressResponse | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/progress/${jobId}`)
        if (!res.ok) throw new Error("Failed to fetch progress")
        const data: ProgressResponse = await res.json()
        setStatus(data)
        if (data.status === "finished" || data.status === "error") {
          if (intervalRef.current) clearInterval(intervalRef.current)
        }
      } catch {
        if (intervalRef.current) clearInterval(intervalRef.current)
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 1200)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [jobId])

  return status
}
```

### 3.8 `frontend/src/lib/api.ts`

```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? ""

export async function uploadFile(file: File): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? "Upload failed")
  }
  return res.json()
}

export async function fetchResults(jobId: string, withViz = false) {
  const url = `${API_BASE}/results/${jobId}${withViz ? "?viz=true" : ""}`
  const res = await fetch(url)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? "Failed to fetch results")
  }
  return res.json()
}

export function downloadUrl(jobId: string) {
  return `${API_BASE}/download/${jobId}`
}
```

### 3.9 `frontend/src/components/DropZone.tsx`

```tsx
import { useState, useCallback } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface DropZoneProps {
  onFile: (file: File) => void
  disabled?: boolean
}

const ACCEPTED = ["application/pdf", "image/png", "image/jpeg", "image/webp", "image/tiff", "image/bmp"]
const ACCEPTED_EXT = ".pdf,.png,.jpg,.jpeg,.webp,.tiff,.bmp"

export function DropZone({ onFile, disabled }: DropZoneProps) {
  const [dragging, setDragging] = useState(false)

  const handleFile = useCallback(
    (file: File) => {
      if (disabled) return
      if (!ACCEPTED.includes(file.type) && !file.name.match(/\.(pdf|png|jpe?g|webp|tiff?|bmp)$/i)) return
      onFile(file)
    },
    [onFile, disabled]
  )

  return (
    <Card
      className={[
        "relative flex flex-col items-center justify-center gap-3 cursor-pointer select-none",
        "border-2 border-dashed rounded-xl p-10 transition-colors",
        dragging ? "border-zinc-400 bg-zinc-50" : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50/50",
        disabled ? "opacity-50 cursor-not-allowed" : "",
      ].join(" ")}
      onClick={() => {
        if (disabled) return
        document.getElementById("file-input")?.click()
      }}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFile(file)
      }}
    >
      <input
        id="file-input"
        type="file"
        accept={ACCEPTED_EXT}
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        disabled={disabled}
      />
      <div className="text-3xl text-zinc-300">↑</div>
      <p className="text-sm font-medium text-zinc-600">
        Drop a file here or <span className="text-zinc-900 underline underline-offset-2">browse</span>
      </p>
      <div className="flex flex-wrap gap-1.5 justify-center">
        {["PDF", "PNG", "JPG", "WEBP", "TIFF"].map((ext) => (
          <Badge key={ext} variant="secondary" className="text-[10px] font-mono">{ext}</Badge>
        ))}
      </div>
      <p className="text-xs text-zinc-400">Max 10 MB</p>
    </Card>
  )
}
```

### 3.10 `frontend/src/components/JobProgress.tsx`

```tsx
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import type { ProgressResponse } from "@/types"

interface JobProgressProps {
  status: ProgressResponse
}

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  processing: "Processing",
  finished: "Done",
  error: "Error",
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  queued: "secondary",
  processing: "default",
  finished: "default",
  error: "destructive",
}

export function JobProgress({ status }: JobProgressProps) {
  const percent =
    status.status === "finished"
      ? 100
      : status.total > 0
      ? Math.round((status.processed / status.total) * 100)
      : status.status === "processing"
      ? 40
      : 5

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-600 truncate max-w-[70%]">{status.message}</p>
        <Badge variant={STATUS_VARIANT[status.status] ?? "secondary"}>
          {STATUS_LABEL[status.status] ?? status.status}
        </Badge>
      </div>
      <Progress value={percent} className="h-1.5" />
      {status.total > 0 && (
        <p className="text-xs text-zinc-400 text-right">
          {status.processed} / {status.total} pages
        </p>
      )}
    </div>
  )
}
```

### 3.11 `frontend/src/components/ResultsPanel.tsx`

```tsx
import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { fetchResults, downloadUrl } from "@/lib/api"
import type { ResultsResponse } from "@/types"

interface ResultsPanelProps {
  jobId: string
}

export function ResultsPanel({ jobId }: ResultsPanelProps) {
  const [data, setData] = useState<ResultsResponse | null>(null)
  const [withViz, setWithViz] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchResults(jobId, withViz)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [jobId, withViz])

  if (loading) return <p className="text-sm text-zinc-400">Loading results…</p>
  if (error) return <p className="text-sm text-red-500">{error}</p>
  if (!data) return null

  const summary = data.summary
  const rows = summary?.type === "pdf" ? summary.pages ?? [] : []
  const items = summary?.type === "image" ? summary.items ?? [] : []

  const totalLines = rows.reduce((s, p) => s + p.lines, 0) + items.reduce((s, i) => s + i.lines, 0)
  const totalRects = rows.reduce((s, p) => s + p.rectangles, 0) + items.reduce((s, i) => s + i.rectangles, 0)
  const totalUnits = rows.length || items.length || 1

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: summary?.type === "pdf" ? "Pages" : "Images", value: totalUnits },
          { label: "Lines", value: totalLines },
          { label: "Rectangles", value: totalRects },
        ].map(({ label, value }) => (
          <Card key={label} className="p-3 text-center">
            <p className="text-2xl font-bold text-zinc-900">{value}</p>
            <p className="text-xs text-zinc-500 mt-0.5">{label}</p>
          </Card>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        <Button asChild size="sm" variant="default">
          <a href={downloadUrl(jobId)} download={data.download_filename}>
            Download JSON
          </a>
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => { setWithViz(!withViz); setLoading(true) }}
        >
          {withViz ? "Hide visuals" : "Load visuals"}
        </Button>
      </div>

      {/* Detection params */}
      {data.detection_params && (
        <>
          <Separator />
          <div>
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-2">Detection params</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(data.detection_params).map(([k, v]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-zinc-500 font-mono">{k}</span>
                  <span className="text-zinc-800 font-mono">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Page/image table */}
      {(rows.length > 0 || items.length > 0) && (
        <>
          <Separator />
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-100">
                  <th className="text-left pb-2 text-zinc-400 font-medium">
                    {summary?.type === "pdf" ? "Page" : "File"}
                  </th>
                  <th className="text-right pb-2 text-zinc-400 font-medium">Lines</th>
                  <th className="text-right pb-2 text-zinc-400 font-medium">Rects</th>
                  <th className="text-right pb-2 text-zinc-400 font-medium">Size</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.page} className="border-b border-zinc-50">
                    <td className="py-1.5 text-zinc-700">{p.page}</td>
                    <td className="py-1.5 text-right text-zinc-700">{p.lines}</td>
                    <td className="py-1.5 text-right text-zinc-700">{p.rectangles}</td>
                    <td className="py-1.5 text-right text-zinc-400">
                      {p.size[0] && p.size[1] ? `${p.size[0]}×${p.size[1]}` : "—"}
                    </td>
                  </tr>
                ))}
                {items.map((i) => (
                  <tr key={i.name} className="border-b border-zinc-50">
                    <td className="py-1.5 text-zinc-700 truncate max-w-[120px]">{i.name}</td>
                    <td className="py-1.5 text-right text-zinc-700">{i.lines}</td>
                    <td className="py-1.5 text-right text-zinc-700">{i.rectangles}</td>
                    <td className="py-1.5 text-right text-zinc-400">
                      {i.dimensions[0] && i.dimensions[1] ? `${i.dimensions[0]}×${i.dimensions[1]}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Visualizations (only when loaded) */}
      {withViz && data.visualizations.length > 0 && (
        <>
          <Separator />
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">Detections</p>
          <div className="grid grid-cols-2 gap-3">
            {data.visualizations.map((v) => (
              <figure key={v.label} className="space-y-1">
                <img src={v.data_url} alt={v.label} className="w-full rounded-lg border border-zinc-100" />
                <figcaption className="text-xs text-zinc-400 text-center">{v.label}</figcaption>
              </figure>
            ))}
          </div>
        </>
      )}

      {/* Raw JSON */}
      <Separator />
      <div>
        <p className="text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-2">Raw JSON</p>
        <pre className="text-[10px] bg-zinc-50 border border-zinc-100 rounded-lg p-3 overflow-auto max-h-64 text-zinc-700 leading-relaxed">
          {data.result_json}
        </pre>
      </div>
    </div>
  )
}
```

### 3.12 `frontend/src/App.tsx`

```tsx
import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { DropZone } from "@/components/DropZone"
import { JobProgress } from "@/components/JobProgress"
import { ResultsPanel } from "@/components/ResultsPanel"
import { useJobPolling } from "@/hooks/useJobPolling"
import { uploadFile } from "@/lib/api"

export default function App() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const pollStatus = useJobPolling(jobId)
  const isProcessing = uploading || (pollStatus?.status === "queued" || pollStatus?.status === "processing")
  const isDone = pollStatus?.status === "finished"

  const handleFile = async (file: File) => {
    setUploadError(null)
    setJobId(null)
    setUploading(true)
    try {
      const { job_id } = await uploadFile(file)
      setJobId(job_id)
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-zinc-100 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-zinc-900 tracking-tight">Skalu</h1>
            <p className="text-xs text-zinc-400">Document structure detector</p>
          </div>
          <span className="text-[10px] font-mono bg-zinc-100 text-zinc-500 px-2 py-1 rounded">v1.0.1</span>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-2xl mx-auto px-6 py-8 space-y-5">
        {/* Upload card */}
        <Card className="p-5 space-y-4 shadow-sm">
          <div>
            <h2 className="text-sm font-semibold text-zinc-800">Upload document</h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Detect horizontal lines and rectangles in PDFs or images
            </p>
          </div>
          <DropZone onFile={handleFile} disabled={isProcessing} />

          {uploadError && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {uploadError}
            </p>
          )}

          {pollStatus && (
            <>
              <Separator />
              <JobProgress status={pollStatus} />
            </>
          )}

          {pollStatus?.status === "error" && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {pollStatus.error ?? "An error occurred during processing."}
            </p>
          )}
        </Card>

        {/* Results card */}
        {isDone && jobId && (
          <Card className="p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-zinc-800 mb-4">Results</h2>
            <ResultsPanel jobId={jobId} />
          </Card>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-100 px-6 py-4 mt-8">
        <p className="text-xs text-zinc-400 text-center max-w-2xl mx-auto">
          Built by{" "}
          <a href="https://github.com/ragaeeb/skalu" className="underline underline-offset-2" target="_blank" rel="noreferrer">
            ragaeeb
          </a>
          . Source on GitHub.
        </p>
      </footer>
    </div>
  )
}
```

### 3.13 `frontend/src/main.tsx`

```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import App from "./App.tsx"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

### 3.14 `frontend/.env.example`

```
# Copy to .env.local for local development
# In production this is injected at build time by GitHub Actions
VITE_API_URL=https://skalu-api-HASH-uc.a.run.app
```

### 3.15 `frontend/firebase.json`

```json
{
  "hosting": {
    "public": "dist",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      {
        "source": "**",
        "destination": "/index.html"
      }
    ],
    "headers": [
      {
        "source": "**/*.@(js|css)",
        "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }]
      },
      {
        "source": "**",
        "headers": [{ "key": "X-Content-Type-Options", "value": "nosniff" }]
      }
    ]
  }
}
```

### 3.16 `frontend/.firebaserc`

```json
{
  "projects": {
    "default": "YOUR_GCP_PROJECT_ID"
  }
}
```

> Replace `YOUR_GCP_PROJECT_ID` with the actual GCP project ID after infrastructure is provisioned.

---

## 4. Infrastructure as Code — `infra/` Directory

Create a new `infra/` directory at the repo root containing all Terraform configuration. This provisions Cloud Run, Firebase Hosting, Artifact Registry, and Workload Identity Federation for GitHub Actions.

### 4.1 `infra/versions.tf`

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Store state in GCS (bucket created manually once — see CLOUD_SETUP.md)
  backend "gcs" {
    bucket = "skalu-tfstate"
    prefix = "terraform/state"
  }
}
```

### 4.2 `infra/variables.tf`

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "github_owner" {
  description = "GitHub organisation or username"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (without owner)"
  type        = string
}

variable "allowed_origins" {
  description = "Comma-separated list of allowed CORS origins for the API"
  type        = string
}
```

### 4.3 `infra/main.tf`

```hcl
provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable required APIs ──────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ── Artifact Registry (Docker images) ────────────────────────────────────
resource "google_artifact_registry_repository" "skalu" {
  depends_on    = [google_project_service.apis]
  location      = var.region
  repository_id = "skalu"
  format        = "DOCKER"
  description   = "Skalu API container images"
}

# ── Cloud Run service (Flask API) ─────────────────────────────────────────
resource "google_cloud_run_v2_service" "api" {
  depends_on = [google_project_service.apis]
  name       = "skalu-api"
  location   = var.region

  template {
    scaling {
      min_instance_count = 1   # Keep warm so background threads don't freeze
      max_instance_count = 2
    }

    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    containers {
      # Image is updated by CI/CD — initial placeholder
      image = "${var.region}-docker.pkg.dev/${var.project_id}/skalu/api:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = false   # CPU always allocated (no throttling on background threads)
        startup_cpu_boost = true
      }

      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name  = "PORT"
        value = "8080"
      }
      env {
        name  = "MAX_CONTENT_LENGTH"
        value = "10485760"
      }

      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 10
      }

      liveness_probe {
        http_get { path = "/health" }
        period_seconds    = 30
        failure_threshold = 3
      }
    }

    # No CPU throttling after request — essential for background processing threads
    annotations = {
      "run.googleapis.com/cpu-throttling" = "false"
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated access to Cloud Run (public API)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.api.project
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Workload Identity Federation for GitHub Actions ───────────────────────
resource "google_iam_workload_identity_pool" "github" {
  depends_on                = [google_project_service.apis]
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions CI/CD"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC Provider"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.actor"      = "assertion.actor"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "attribute.repository == '${var.github_owner}/${var.github_repo}'"
}

# Service account used by GitHub Actions
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-sa"
  display_name = "GitHub Actions Service Account"
  description  = "Used by GitHub Actions to deploy Skalu"
}

# Grant GitHub Actions SA the necessary roles
locals {
  github_sa_roles = [
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/firebase.admin",
  ]
}

resource "google_project_iam_member" "github_actions_roles" {
  for_each = toset(local.github_sa_roles)
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}

# Bind WIF pool to service account — scope to this repo only
resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.github_repo}"
}
```

### 4.4 `infra/outputs.tf`

```hcl
output "api_url" {
  description = "Cloud Run API service URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "artifact_registry_repo" {
  description = "Docker image repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/skalu/api"
}

output "workload_identity_provider" {
  description = "WIF provider — add as GCP_WORKLOAD_IDENTITY_PROVIDER GitHub secret"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_actions_service_account" {
  description = "SA email — add as GCP_SERVICE_ACCOUNT GitHub secret"
  value       = google_service_account.github_actions.email
}
```

### 4.5 `infra/terraform.tfvars.example`

```hcl
# Copy to terraform.tfvars (git-ignored) and fill in values
project_id      = "your-gcp-project-id"
region          = "us-central1"
github_owner    = "your-github-username"
github_repo     = "skalu"
allowed_origins = "https://your-project.web.app,https://your-project.firebaseapp.com"
```

Add `infra/terraform.tfvars` to `.gitignore`.

---

## 5. CI/CD — GitHub Actions

Replace `.github/workflows/release.yml`. Update `.github/workflows/test.yml`. Add two new deploy workflows.

### 5.1 `.github/workflows/test.yml` (updated)

```yaml
name: Tests

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv with Python 3.13
        uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"
          enable-cache: true

      - name: Create virtual environment
        run: uv venv --python 3.13

      - name: Install dependencies
        run: uv pip install -r requirements_dev.txt

      - name: Run tests
        run: uv run pytest --cov=skalu --cov-report=term
```

### 5.2 `.github/workflows/release.yml` (updated)

```yaml
name: Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Set up Python 3.13
        uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"
          enable-cache: true

      - name: Install Python Semantic Release
        run: uv tool install --no-progress python-semantic-release

      - name: Semantic Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          semantic-release version
          semantic-release publish
```

### 5.3 `.github/workflows/deploy-api.yml` (new)

```yaml
name: Deploy API to Cloud Run

on:
  push:
    branches: [main]
    paths:
      - "app.py"
      - "demo_utils.py"
      - "skalu.py"
      - "requirements.txt"
      - "Dockerfile"

  workflow_dispatch:

permissions:
  contents: read
  id-token: write   # Required for Workload Identity Federation

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: us-central1
  SERVICE: skalu-api
  REGISTRY: us-central1-docker.pkg.dev

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to Google Cloud (keyless via WIF)
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Configure Docker for Artifact Registry
        run: gcloud auth configure-docker ${{ env.REGISTRY }} --quiet

      - name: Build and push Docker image
        run: |
          IMAGE="${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/skalu/api:${{ github.sha }}"
          docker build -t "${IMAGE}" -t "${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/skalu/api:latest" .
          docker push "${IMAGE}"
          docker push "${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/skalu/api:latest"

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy ${{ env.SERVICE }} \
            --image "${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/skalu/api:${{ github.sha }}" \
            --region ${{ env.REGION }} \
            --no-cpu-throttling \
            --min-instances 1 \
            --max-instances 2 \
            --memory 1Gi \
            --timeout 3600 \
            --allow-unauthenticated \
            --project ${{ env.PROJECT_ID }} \
            --quiet

      - name: Output service URL
        run: |
          gcloud run services describe ${{ env.SERVICE }} \
            --region ${{ env.REGION }} \
            --format "value(status.url)" \
            --project ${{ env.PROJECT_ID }}
```

### 5.4 `.github/workflows/deploy-frontend.yml` (new)

```yaml
name: Deploy Frontend to Firebase Hosting

on:
  push:
    branches: [main]
    paths:
      - "frontend/**"

  workflow_dispatch:

permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci

      - name: Build frontend
        working-directory: frontend
        env:
          VITE_API_URL: ${{ secrets.VITE_API_URL }}
        run: npm run build

      - name: Deploy to Firebase Hosting
        working-directory: frontend
        run: |
          npm install -g firebase-tools
          firebase deploy --only hosting --token "${{ secrets.FIREBASE_TOKEN }}" --project ${{ secrets.GCP_PROJECT_ID }}
```

---

## 6. GitHub Secrets Required

After Terraform is applied, add the following secrets to the GitHub repository (`Settings → Secrets → Actions`):

| Secret name | Value | Where to get it |
|---|---|---|
| `GCP_PROJECT_ID` | Your GCP project ID | GCP Console |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Output from `terraform output workload_identity_provider` | Terraform |
| `GCP_SERVICE_ACCOUNT` | Output from `terraform output github_actions_service_account` | Terraform |
| `VITE_API_URL` | Output from `terraform output api_url` | Terraform |
| `FIREBASE_TOKEN` | From `firebase login:ci` | Local machine |

---

## 7. `.gitignore` Additions

Add these entries to `.gitignore`:

```
# Terraform
infra/.terraform/
infra/.terraform.lock.hcl
infra/terraform.tfvars
infra/*.tfstate
infra/*.tfstate.backup

# Frontend
frontend/node_modules/
frontend/dist/
frontend/.env.local

# General
*.env
```

---

## 8. Production-Grade Checklist

The agent should verify each of these after implementing all changes:

- [ ] `GET /health` returns `{"status": "ok"}` with HTTP 200
- [ ] CORS headers are present on API responses with the correct origin
- [ ] `Content-Encoding: gzip` is present on JSON responses (flask-compress working)
- [ ] Background thread completes after HTTP response is returned (CPU not throttling)
- [ ] Temp directories are cleaned up in the `finally` block after each job
- [ ] Docker image starts on port `$PORT` (defaults to 8080)
- [ ] `gunicorn --timeout 3600` is set to handle large PDF processing
- [ ] `--no-cpu-throttling` is set in Cloud Run deployment (or `cpu_idle = false` in Terraform)
- [ ] `min_instance_count = 1` is set so in-memory job dict is reliable
- [ ] Terraform state bucket exists before `terraform init`
- [ ] Streamlit, render.yaml, and templates/ are fully removed from the repo
- [ ] Frontend builds without errors: `npm run build` in `frontend/`
- [ ] All four GitHub secrets are set before pushing a deploy-triggering commit