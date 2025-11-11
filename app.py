import base64
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from typing import Dict, List, Optional

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.utils import secure_filename

from skalu import process_pdf, process_single_image

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "bmp", "tiff", "webp"}

DEFAULT_PARAMS = {
    "min_line_width_ratio": 0.2,
    "max_line_height": 10,
    "min_rect_area_ratio": 0.001,
    "max_rect_area_ratio": 0.5,
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "skalu-demo-secret")
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))

_jobs: Dict[str, Dict] = {}
_jobs_lock = threading.Lock()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_summary(data: dict) -> Optional[dict]:
    if not data:
        return None

    if "result" in data:
        items = []
        for name, info in data["result"].items():
            lines = len(info.get("horizontal_lines", []))
            rectangles = len(info.get("rectangles", []))
            items.append(
                {
                    "name": name,
                    "lines": lines,
                    "rectangles": rectangles,
                    "dimensions": (
                        info.get("dpi", {}).get("width"),
                        info.get("dpi", {}).get("height"),
                    ),
                }
            )
        return {"type": "image", "items": items}

    if "pages" in data:
        pages = []
        for page in data["pages"]:
            pages.append(
                {
                    "page": page.get("page"),
                    "lines": len(page.get("horizontal_lines", [])),
                    "rectangles": len(page.get("rectangles", [])),
                    "size": (page.get("width"), page.get("height")),
                }
            )
        return {"type": "pdf", "pages": pages}

    return None


def encode_image_as_data_url(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as file:
            encoded = base64.b64encode(file.read()).decode("ascii")
    except OSError:
        app.logger.warning("Unable to read debug image %s", path)
        return None

    ext = os.path.splitext(path)[1].lower()
    if ext in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/octet-stream"

    return f"data:{mime};base64,{encoded}"


def collect_visualizations(workdir: str) -> List[Dict[str, str]]:
    visualizations: List[Dict[str, str]] = []
    if not os.path.isdir(workdir):
        return visualizations

    for name in sorted(os.listdir(workdir)):
        if not name.lower().endswith(("_detected.jpg", "_detected.jpeg", "_detected.png", "_detected.webp")):
            continue

        path = os.path.join(workdir, name)
        data_url = encode_image_as_data_url(path)
        if not data_url:
            continue

        label = "Detections"
        page_match = re.search(r"_page_(\d+)_", name)
        if page_match:
            label = f"Page {int(page_match.group(1))} detections"
        elif "page" in name.lower():
            label = name.rsplit("_detected", 1)[0]

        visualizations.append({"label": label, "data_url": data_url})

    return visualizations


def collect_debug_groups(debug_dir: str) -> List[Dict[str, List[Dict[str, str]]]]:
    groups: List[Dict[str, List[Dict[str, str]]]] = []
    if not debug_dir or not os.path.isdir(debug_dir):
        return groups

    entries = sorted(os.listdir(debug_dir))
    has_subdirs = any(os.path.isdir(os.path.join(debug_dir, entry)) for entry in entries)

    def sort_key(name: str):
        page_match = re.search(r"(\d+)", name)
        return (int(page_match.group(1)) if page_match else float("inf"), name)

    if has_subdirs:
        for entry in sorted(entries, key=sort_key):
            entry_path = os.path.join(debug_dir, entry)
            if not os.path.isdir(entry_path):
                continue

            images = []
            for img_name in sorted(os.listdir(entry_path)):
                if not img_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                data_url = encode_image_as_data_url(os.path.join(entry_path, img_name))
                if data_url:
                    images.append({"name": img_name, "data_url": data_url})

            if images:
                title = entry.replace("_", " ").title()
                page_match = re.search(r"(\d+)", entry)
                if page_match:
                    title = f"Page {int(page_match.group(1))} steps"
                groups.append({"title": title, "images": images})
    else:
        images = []
        for img_name in sorted(entries):
            if not img_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            data_url = encode_image_as_data_url(os.path.join(debug_dir, img_name))
            if data_url:
                images.append({"name": img_name, "data_url": data_url})
        if images:
            groups.append({"title": "Processing steps", "images": images})

    return groups


def _job_progress_message(done: int, total: int, suffix: str) -> str:
    if total:
        if suffix == ".pdf":
            if done >= total:
                return f"Finished all {total} pages"
            next_page = min(done + 1, total)
            return f"Processing page {next_page} of {total}"
        if done >= total:
            return "Processing complete"
        return f"Processed {done} of {total} items"
    if suffix == ".pdf":
        return "Preparing pages"
    return "Processing image"


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
            job["message"] = _job_progress_message(done, total, suffix)

    try:
        with job["lock"]:
            job["status"] = "processing"
            job["message"] = "Starting analysis"

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
            raise RuntimeError("Processing failed. Please try another file.")

        with open(output_json_path, "r", encoding="utf-8") as file:
            result_data = json.load(file)

        result_json = json.dumps(result_data, indent=4, ensure_ascii=False)
        summary = build_summary(result_data)
        debug_groups = collect_debug_groups(debug_dir)
        visualizations = collect_visualizations(workdir)
        download_filename = f"{os.path.splitext(filename)[0]}_results.json"
        detection_params = result_data.get("detection_params")

        payload = {
            "result_json": result_json,
            "result_data": result_data,
            "summary": summary,
            "processed_filename": filename,
            "detection_params": detection_params,
            "debug_groups": debug_groups,
            "visualizations": visualizations,
            "download_filename": download_filename,
        }

        with job["lock"]:
            job["status"] = "finished"
            job["processed"] = job.get("total", 0) or job.get("processed", 0)
            job["message"] = "Processing complete"
            job["result"] = payload
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Job %s failed", job_id)
        with job["lock"]:
            job["status"] = "error"
            job["error"] = str(exc)
            job["message"] = f"Failed: {exc}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        with job["lock"]:
            job["workdir"] = None


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    uploaded_file = request.files.get("file")
    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"error": "Please choose a PDF or image file to analyze."}), 400

    filename = secure_filename(uploaded_file.filename)
    if not allowed_file(filename):
        return jsonify({"error": "Unsupported file type. Please upload a PDF or common image format."}), 400

    suffix = os.path.splitext(filename)[1].lower()

    try:
        workdir = tempfile.mkdtemp(prefix="skalu_job_")
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Failed to allocate workspace")
        return jsonify({"error": f"Unable to prepare workspace: {exc}"}), 500

    input_path = os.path.join(workdir, filename)
    try:
        uploaded_file.save(input_path)
    except Exception as exc:  # pylint: disable=broad-except
        app.logger.exception("Failed to save upload")
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
        "download_filename": None,
        "workdir": workdir,
        "lock": threading.Lock(),
    }

    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_process_job, args=(job_id, suffix), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


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
        }
        if job["status"] == "error":
            response["error"] = job.get("error")
        response["result_ready"] = job.get("status") == "finished"
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

        payload = job["result"].copy()
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
