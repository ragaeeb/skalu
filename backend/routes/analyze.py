"""Analyze endpoint (single-shot JSON + NDJSON stream)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from werkzeug.utils import secure_filename

from demo_utils import allowed_file

from ..errors import AnalysisTimeoutError, BadRequestError, ProcessingError
from ..models import AnalyzeOptions
from ..services.streaming import encode_event_line, run_analysis_with_timeout, stream_analysis_events

analyze_bp = Blueprint("analyze", __name__)


def _save_upload() -> tuple[Path, str]:
    uploaded_file = request.files.get("file")
    if not uploaded_file or uploaded_file.filename == "":
        raise BadRequestError("Please choose a PDF or image file to analyze.")

    filename = secure_filename(uploaded_file.filename)
    if not allowed_file(filename):
        raise BadRequestError("Unsupported file type.")

    workspace = Path(tempfile.mkdtemp(prefix="skalu_run_"))
    try:
        uploaded_path = workspace / filename
        uploaded_file.save(str(uploaded_path))
    except Exception as exc:  # pylint: disable=broad-except
        shutil.rmtree(workspace, ignore_errors=True)
        raise ProcessingError(f"Unable to save uploaded file: {exc}") from exc

    return workspace, filename


@analyze_bp.post("/analyze")
def analyze() -> tuple | Response:
    settings = current_app.config["SETTINGS"]

    try:
        options = AnalyzeOptions.from_form(request.form)
        workspace, filename = _save_upload()
    except ValueError as exc:
        return jsonify(BadRequestError(str(exc)).to_dict()), 400
    except BadRequestError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except ProcessingError as exc:
        return jsonify(exc.to_dict()), 500

    if options.stream:

        @stream_with_context
        def event_generator():
            try:
                for event in stream_analysis_events(
                    str(workspace),
                    filename,
                    options,
                    timeout_seconds=settings.analyze_timeout_seconds,
                    heartbeat_seconds=settings.stream_heartbeat_seconds,
                ):
                    yield encode_event_line(event)
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

        response = Response(event_generator(), mimetype="application/x-ndjson")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    try:
        payload = run_analysis_with_timeout(
            str(workspace),
            filename,
            options,
            timeout_seconds=settings.analyze_timeout_seconds,
        )
        return jsonify(payload), 200
    except AnalysisTimeoutError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    except ProcessingError as exc:
        return jsonify(exc.to_dict()), exc.status_code
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
