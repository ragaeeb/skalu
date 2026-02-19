import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import uuid
from typing import Dict

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_compress import Compress
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename

from demo_utils import (
    DEFAULT_PARAMS,
    allowed_file,
    build_summary,
    collect_debug_groups,
    collect_visualizations,
    encode_image_as_data_url,
    job_progress_message,
)
from skalu import process_pdf, process_single_image

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s"}',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "skalu-demo-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)
)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else "*"
CORS(app, origins=_origins, supports_credentials=False)
Compress(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "30 per hour"],
    storage_uri="memory://",
)

_jobs: Dict[str, Dict] = {}
_jobs_lock = threading.Lock()


def _parse_bool(value: str | None, default: bool) -> bool:
    """Parse truthy/falsey string values from request form fields."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_progress_event(job: Dict) -> Dict:
    """Build a progress payload for SSE/progress responses."""
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
    return response


def _publish_job_event(job: Dict) -> None:
    """Append a new event snapshot and notify SSE listeners."""
    event = _build_progress_event(job)
    job["event_seq"] += 1
    event["seq"] = job["event_seq"]
    job["events"].append(event)
    if len(job["events"]) > 500:
        job["events"] = job["events"][-500:]
    job["event_cond"].notify_all()


def _coerce_detection_params(raw: dict | None) -> dict:
    """Normalize user-provided detection params with sane defaults."""
    defaults = {
        "min_line_width_ratio": DEFAULT_PARAMS.get("min_line_width_ratio", 0.2),
        "max_line_height": DEFAULT_PARAMS.get("max_line_height", 10),
        "min_rect_area_ratio": DEFAULT_PARAMS.get("min_rect_area_ratio", 0.001),
        "max_rect_area_ratio": DEFAULT_PARAMS.get("max_rect_area_ratio", 0.5),
    }
    if not isinstance(raw, dict):
        return defaults

    normalized = defaults.copy()
    for key in normalized:
        if key not in raw:
            continue
        value = raw.get(key)
        try:
            if key == "max_line_height":
                normalized[key] = max(1, int(float(value)))
            else:
                normalized[key] = float(value)
        except (TypeError, ValueError):
            continue

    # Ensure min area ratio is never greater than max area ratio.
    if normalized["min_rect_area_ratio"] > normalized["max_rect_area_ratio"]:
        normalized["min_rect_area_ratio"] = normalized["max_rect_area_ratio"]

    return normalized


def _process_job(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return

    workdir = job["workdir"]
    filename = job["filename"]
    suffix = job["suffix"]
    input_path = os.path.join(workdir, filename)
    output_json_path = os.path.join(workdir, "results.json")
    debug_dir = os.path.join(workdir, "debug")

    def progress_callback(done: int, total: int) -> None:
        with job["lock"]:
            job["processed"] = done
            job["total"] = total
            job["status"] = "processing"
            job["message"] = job_progress_message(done, total, suffix)
            _publish_job_event(job)

    try:
        with job["lock"]:
            job["status"] = "processing"
            job["message"] = "Starting analysis"
            _publish_job_event(job)

        logger.info("Starting job %s for file %s", job_id, filename)

        detection_params = job.get("detection_params") or _coerce_detection_params(None)
        include_empty_pages = bool(
            job.get("include_empty_pages", DEFAULT_PARAMS.get("include_empty_pages", True))
        )
        save_visualization = bool(job.get("save_visualization", False))

        if suffix == ".pdf":
            success = process_pdf(
                input_path,
                output_json_path,
                params=detection_params,
                debug_dir=debug_dir,
                save_visualization=save_visualization,
                progress_callback=progress_callback,
                include_empty_pages=include_empty_pages,
            )
        else:
            success = process_single_image(
                input_path,
                output_json_path,
                params=detection_params,
                debug_dir=debug_dir,
                save_visualization=save_visualization,
                progress_callback=progress_callback,
            )

        if not success:
            raise RuntimeError("Processing failed - please try another file.")

        with open(output_json_path, "r", encoding="utf-8") as fh:
            result_data = json.load(fh)

        result_json = json.dumps(result_data, indent=4, ensure_ascii=False)
        summary = build_summary(result_data)

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
            "_visualizations": visualizations,
            "_debug_groups": debug_groups,
            "download_filename": download_filename,
        }

        with job["lock"]:
            job["status"] = "finished"
            job["processed"] = job.get("total", 0) or job.get("processed", 0)
            job["message"] = "Processing complete"
            job["result"] = payload
            _publish_job_event(job)

        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Job %s failed: %s", job_id, exc)
        with job["lock"]:
            job["status"] = "error"
            job["error"] = str(exc)
            job["message"] = f"Failed: {exc}"
            _publish_job_event(job)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        with job["lock"]:
            job["workdir"] = None


@app.route("/health", methods=["GET"])
@limiter.exempt
def health():
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
        "suffix": suffix,
        "include_empty_pages": DEFAULT_PARAMS.get("include_empty_pages", True),
        "save_visualization": False,
        "detection_params": _coerce_detection_params(None),
        "status": "uploaded",
        "processed": 0,
        "total": 0,
        "message": "File uploaded. Configure options, then click Process.",
        "error": None,
        "result": None,
        "workdir": workdir,
        "lock": threading.Lock(),
    }
    job["event_cond"] = threading.Condition(job["lock"])
    job["event_seq"] = 0
    job["events"] = []

    with _jobs_lock:
        _jobs[job_id] = job

    with job["lock"]:
        _publish_job_event(job)

    logger.info("Uploaded job %s for file %s", job_id, filename)
    return jsonify({"job_id": job_id, "status": "uploaded"}), 202


@app.route("/process/<job_id>", methods=["POST"])
def process(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    payload = request.get_json(silent=True) or {}
    include_empty_pages = _parse_bool(
        str(payload.get("include_empty_pages")) if "include_empty_pages" in payload else None,
        DEFAULT_PARAMS.get("include_empty_pages", True),
    )
    save_visualization = _parse_bool(
        str(payload.get("save_visualization")) if "save_visualization" in payload else None,
        False,
    )
    detection_params = _coerce_detection_params(payload.get("detection_params"))

    with job["lock"]:
        if job["status"] == "processing":
            return jsonify({"error": "Job is already processing"}), 409
        if job["status"] == "finished":
            return jsonify({"error": "Job already processed"}), 409
        if not job.get("workdir"):
            return jsonify({"error": "Job workspace is unavailable"}), 400

        job["include_empty_pages"] = include_empty_pages
        job["save_visualization"] = save_visualization
        job["detection_params"] = detection_params
        job["status"] = "queued"
        job["processed"] = 0
        job["total"] = 0
        job["message"] = "Queued"
        job["error"] = None
        job["result"] = None
        _publish_job_event(job)

    thread = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
    thread.start()
    logger.info("Queued processing for job %s", job_id)
    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route("/progress/<job_id>", methods=["GET"])
@limiter.exempt
def progress(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    with job["lock"]:
        response = _build_progress_event(job)
    return jsonify(response)


@app.route("/events/<job_id>", methods=["GET"])
@limiter.exempt
def events(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    def event_stream():
        last_seq = 0
        # Ask the browser to reconnect in case the stream is interrupted.
        yield "retry: 2000\n\n"
        while True:
            pending = []
            current_status = ""
            with job["lock"]:
                pending = [event for event in job["events"] if event["seq"] > last_seq]
                if not pending and job["status"] not in ("finished", "error"):
                    job["event_cond"].wait(timeout=15)
                    pending = [event for event in job["events"] if event["seq"] > last_seq]
                current_status = job["status"]

            if pending:
                for event in pending:
                    last_seq = event["seq"]
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                if pending[-1]["status"] in ("finished", "error"):
                    break
            else:
                # Keep proxies/connections alive while waiting for updates.
                yield ": keepalive\n\n"
                if current_status in ("finished", "error"):
                    break

    response = Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


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
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
