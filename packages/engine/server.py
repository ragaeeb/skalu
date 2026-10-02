"""Private, disposable native engine. Only the Worker binding can reach it."""
import json
import math
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid

from flask import Flask, jsonify, request, send_file

VERSION = "2.0.0"  # x-release-please-version
PROTOCOL = 1
MAX_BYTES = 256 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_TOTAL_PIXELS = 1_000_000_000
MAX_PAGES = 1000
ROOT = Path(tempfile.gettempdir()) / "skalu-engine"
ROOT.mkdir(exist_ok=True)
PROCESSING = threading.Lock()
CONTROL = threading.RLock()
ACTIVE = {}
CANCELLED = {}
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


def job_dir(job_id):
    if str(uuid.UUID(job_id)) != job_id:
        raise ValueError("Invalid job ID.")
    return ROOT / job_id


def execute_task(action, directory, page, params, receipt):
    """Hard bounds apply inside a killable child, including PDF inspection."""
    try:
        if os.name == "posix":
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
            if os.uname().sysname == "Linux":
                resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
        import pymupdf as fitz
        from skalu import process_pdf
        source = directory / "source.pdf"
        if action == "inspect":
            with fitz.open(source) as document:
                if not document.is_pdf or document.needs_pass:
                    raise ValueError("Upload an unencrypted PDF.")
                if not 1 <= len(document) <= MAX_PAGES:
                    raise ValueError(f"PDF must contain 1–{MAX_PAGES} pages.")
                total_pixels = 0
                for pdf_page in document:
                    width = math.ceil(pdf_page.rect.width * 2)
                    height = math.ceil(pdf_page.rect.height * 2)
                    if width < 1 or height < 1 or width * height > MAX_PIXELS:
                        raise ValueError("PDF page exceeds the 16 megapixel render limit.")
                    total_pixels += width * height
                if total_pixels > MAX_TOTAL_PIXELS:
                    raise ValueError("PDF exceeds the cumulative render limit; split it into smaller PDFs.")
                result = {"total": len(document), "engine_version": VERSION, "protocol": PROTOCOL}
        else:
            output = directory / f"page-{page}"
            output.mkdir(exist_ok=True)
            success = process_pdf(str(source), str(output / "result.json"), params=params,
                                  save_visualization=True, include_empty_pages=True, page_numbers=[page - 1], max_pixels=MAX_PIXELS)
            if not success:
                raise ValueError("PDF could not be processed.")
            if (output / "result.json").stat().st_size > 1024 * 1024:
                raise ValueError("Page detection result exceeds 1 MiB.")
            image = output / f"source_page_{page}_detected.jpg"
            if image.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("Page visualization exceeds 8 MiB.")
            result = json.loads((output / "result.json").read_text())
        receipt.write_text(json.dumps({"result": result}))
    except Exception as error:
        message = str(error)[:500] if isinstance(error, ValueError) else "PDF is corrupt or could not be processed."
        receipt.write_text(json.dumps({"error": message}))


def stop_process(process):
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join()


def cancel_job(job_id):
    directory = job_dir(job_id)
    with CONTROL:
        now = time.monotonic()
        for key, deadline in list(CANCELLED.items()):
            if deadline <= now:
                del CANCELLED[key]
        CANCELLED[job_id] = now + 180
        process = ACTIVE.get(job_id)
        if process is not None:
            stop_process(process)
        shutil.rmtree(directory, ignore_errors=True)


def ensure_active(directory):
    if CANCELLED.get(directory.name, 0) > time.monotonic():
        raise ValueError("Job cancelled.")


def run_task(action, directory, page=0, params=None):
    # Waiting requests must observe cancellation without occupying all control threads.
    while not PROCESSING.acquire(timeout=0.05):
        with CONTROL:
            ensure_active(directory)
    try:
        with tempfile.TemporaryDirectory() as temporary:
            receipt = Path(temporary) / "receipt.json"
            with CONTROL:
                ensure_active(directory)
                process = multiprocessing.get_context("spawn").Process(
                    target=execute_task, args=(action, directory, page, params, receipt))
                process.start()
                ACTIVE[directory.name] = process
            try:
                process.join(65)
                with CONTROL:
                    if process.is_alive():
                        stop_process(process)
                        raise TimeoutError("PDF inspection or page processing exceeded 65 seconds.")
                    ensure_active(directory)
                if process.exitcode != 0 or not receipt.exists():
                    raise ValueError("Engine resource limit exceeded.")
                result = json.loads(receipt.read_text())
                if "error" in result:
                    raise ValueError(result["error"])
                return result["result"]
            finally:
                with CONTROL:
                    ACTIVE.pop(directory.name, None)
                    process.close()
    finally:
        PROCESSING.release()


@app.get("/health")
def health():
    return jsonify(version=VERSION, protocol=PROTOCOL)


@app.route("/jobs/<job_id>", methods=["PUT", "DELETE"])
def source(job_id):
    directory = job_dir(job_id)
    if request.method == "DELETE":
        cancel_job(job_id)
        return "", 204
    with CONTROL:
        ensure_active(directory)
        directory.mkdir(exist_ok=True)
    source = directory / "source.pdf"
    if source.exists():
        # Retries still send an R2 stream; consume it before responding so the caller's upload can finish.
        while request.stream.read(1024 * 1024):
            pass
        return jsonify(run_task("inspect", directory))
    try:
        temporary = directory / "upload.tmp"
        size = 0
        with temporary.open("wb") as output:
            while chunk := request.stream.read(1024 * 1024):
                with CONTROL:
                    ensure_active(directory)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("PDF exceeds 256 MiB.")
                output.write(chunk)
        if size < 5:
            raise ValueError("Empty PDF.")
        temporary.replace(source)
        return jsonify(run_task("inspect", directory))
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


@app.post("/jobs/<job_id>/pages/<int:page>")
def analyze(job_id, page):
    directory = job_dir(job_id)
    if not (directory / "source.pdf").exists():
        return jsonify(error="Source cache missing"), 404
    if not 1 <= page <= MAX_PAGES:
        raise ValueError("Invalid page number.")
    return jsonify({**run_task("page", directory, page, request.get_json()),
                    "engine_version": VERSION, "protocol": PROTOCOL})


@app.get("/jobs/<job_id>/pages/<int:page>/image")
def image(job_id, page):
    directory = job_dir(job_id) / f"page-{page}"
    path = directory / f"source_page_{page}_detected.jpg"
    if not path.exists():
        return jsonify(error="Page cache missing"), 404
    response = send_file(path, mimetype="image/jpeg")
    # send_file owns an open descriptor; unlink keeps disk usage bounded.
    shutil.rmtree(directory, ignore_errors=True)
    return response


@app.errorhandler(ValueError)
def invalid(error):
    return jsonify(error=str(error)), 422


@app.errorhandler(TimeoutError)
def timeout(error):
    return jsonify(error=str(error)), 504


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
