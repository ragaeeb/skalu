"""Flask application factory for the Skalu document analysis demo."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Dict, MutableMapping, Optional

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.utils import secure_filename

from skalu import process_pdf, process_single_image
from skalu.demo_utils import (
    DEFAULT_PARAMS,
    allowed_file,
    build_summary,
    collect_debug_groups,
    collect_visualizations,
    encode_image_as_data_url,
    job_progress_message,
)

JobMapping = MutableMapping[str, Dict[str, object]]


def _templates_path() -> str:
    """Return the on-disk template directory for the Flask app."""
    return str(Path(__file__).resolve().parent / "templates")


def create_app() -> Flask:
    """Application factory used by the production server and tests."""
    app = Flask(__name__, template_folder=_templates_path())
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "skalu-demo-secret")
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("MAX_CONTENT_LENGTH", 25 * 1024 * 1024)
    )

    jobs: JobMapping = {}
    jobs_lock = threading.Lock()

    def _process_job(job_id: str, suffix: str) -> None:
        with jobs_lock:
            job = jobs.get(job_id)
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
            detection_params: Optional[dict] = result_data.get("detection_params")

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
            app.logger.exception("Job %s failed", job_id)  # type: ignore[attr-defined]
            with job["lock"]:
                job["status"] = "error"
                job["error"] = str(exc)
                job["message"] = f"Failed: {exc}"
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            with job["lock"]:
                job["workdir"] = None

    @app.route("/", methods=["GET"])
    def index() -> str:
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
            app.logger.exception("Failed to allocate workspace")  # type: ignore[attr-defined]
            return jsonify({"error": f"Unable to prepare workspace: {exc}"}), 500

        input_path = os.path.join(workdir, filename)
        try:
            uploaded_file.save(input_path)
        except Exception as exc:  # pylint: disable=broad-except
            app.logger.exception("Failed to save upload")  # type: ignore[attr-defined]
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

        with jobs_lock:
            jobs[job_id] = job

        thread = threading.Thread(target=_process_job, args=(job_id, suffix), daemon=True)
        thread.start()

        return jsonify({"job_id": job_id})

    @app.route("/progress/<job_id>", methods=["GET"])
    def progress(job_id: str):
        with jobs_lock:
            job = jobs.get(job_id)
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
        with jobs_lock:
            job = jobs.get(job_id)
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
        with jobs_lock:
            job = jobs.get(job_id)
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

    return app


def main() -> None:
    """Run a development server."""
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    main()
