"""Analyze endpoint (single-shot JSON + NDJSON stream)."""
from __future__ import annotations

import ipaddress
import socket
import shutil
import tempfile
import hashlib
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from werkzeug.utils import secure_filename

from demo_utils import allowed_file

from ..errors import AnalysisTimeoutError, BadRequestError, ProcessingError
from ..models import AnalyzeOptions
from ..services.streaming import encode_event_line, run_analysis_with_timeout, stream_analysis_events

analyze_bp = Blueprint("analyze", __name__)
MAX_REMOTE_FILENAME_CHARS = 120


def _is_allowed_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = parsed.hostname
    if not host:
        return False

    lowered = host.lower()
    if lowered in {"localhost", "metadata.google.internal"}:
        return False

    try:
        resolved = socket.getaddrinfo(host, None)
    except OSError:
        return False

    for result in resolved:
        ip = result[4][0]
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return False

        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            return False

    return True


def _build_remote_filename(url: str) -> str:
    parsed = urlparse(url)
    basename = Path(parsed.path).name or "remote.pdf"
    secured = secure_filename(basename)

    stem = Path(secured).stem or "remote"
    suffix = Path(secured).suffix.lower()
    if suffix != ".pdf":
        suffix = ".pdf"

    filename = f"{stem}{suffix}"
    if len(filename) <= MAX_REMOTE_FILENAME_CHARS:
        return filename

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    reserved = len(suffix) + len(digest) + 1
    max_stem_len = max(1, MAX_REMOTE_FILENAME_CHARS - reserved)
    truncated_stem = stem[:max_stem_len]
    return f"{truncated_stem}_{digest}{suffix}"


def fetch_remote_pdf(url: str, workspace: Path, max_bytes: int) -> str:
    if not _is_allowed_public_url(url):
        raise BadRequestError("file_url must be a public http(s) URL.")

    filename = _build_remote_filename(url)

    destination = workspace / filename
    request_obj = Request(
        url,
        headers={
            "User-Agent": "skalu/1.0",
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.1",
        },
    )

    try:
        with urlopen(request_obj, timeout=15) as response:  # nosec B310
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        raise BadRequestError("Remote file is too large.")
                except ValueError:
                    pass

            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "pdf" not in content_type and "octet-stream" not in content_type:
                raise BadRequestError("file_url did not return a PDF.")

            downloaded = 0
            with destination.open("wb") as output:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise BadRequestError("Remote file is too large.")
                    output.write(chunk)
    except BadRequestError:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        raise ProcessingError(f"Unable to download file_url: {exc}") from exc

    if destination.stat().st_size == 0:
        raise BadRequestError("Downloaded file was empty.")

    return filename


def _save_input_file(max_bytes: int) -> tuple[Path, str]:
    uploaded_file = request.files.get("file")
    file_url = (request.form.get("file_url") or "").strip()

    if uploaded_file and uploaded_file.filename and file_url:
        raise BadRequestError("Provide either file or file_url, not both.")

    if (not uploaded_file or uploaded_file.filename == "") and not file_url:
        raise BadRequestError("Please choose a PDF or image file to analyze.")

    workspace = Path(tempfile.mkdtemp(prefix="skalu_run_"))
    try:
        if file_url:
            filename = fetch_remote_pdf(file_url, workspace, max_bytes=max_bytes)
        else:
            filename = secure_filename(uploaded_file.filename)
            if not allowed_file(filename):
                raise BadRequestError("Unsupported file type.")
            uploaded_path = workspace / filename
            uploaded_file.save(str(uploaded_path))
    except Exception as exc:  # pylint: disable=broad-except
        shutil.rmtree(workspace, ignore_errors=True)
        if isinstance(exc, BadRequestError):
            raise
        raise ProcessingError(f"Unable to save uploaded file: {exc}") from exc

    return workspace, filename


@analyze_bp.post("/analyze")
def analyze() -> tuple | Response:
    settings = current_app.config["SETTINGS"]

    try:
        options = AnalyzeOptions.from_form(request.form)
        workspace, filename = _save_input_file(max_bytes=settings.max_content_length)
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
