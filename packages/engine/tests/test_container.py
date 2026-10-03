"""Native transport and chunk equivalence, using real PDFs rather than renderer mocks."""
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys

import pymupdf as fitz
import pytest
from server import app, job_dir
from skalu import process_pdf
from uuid import uuid4


def test_original_page_chunks_preserve_geometry_and_detection():
    fixture = Path(__file__).parent / "fixtures/madhaban-offset-mediabox-page-1.pdf"
    with tempfile.TemporaryDirectory() as directory:
        full = Path(directory) / "full.json"
        chunk = Path(directory) / "chunk.json"
        assert process_pdf(str(fixture), str(full), include_empty_pages=True)
        assert process_pdf(str(fixture), str(chunk), include_empty_pages=True,
                           page_numbers=[0], max_pixels=16_000_000)
        assert json.loads(full.read_text()) == json.loads(chunk.read_text())


def test_private_engine_upload_process_image_and_cleanup():
    client = app.test_client()
    job_id = str(uuid4())
    with fitz.open() as document:
        page = document.new_page(width=600, height=800)
        page.draw_line((50, 150), (550, 150), width=2)
        document.new_page(width=600, height=800)
        content = document.tobytes()
    try:
        response = client.put(f"/jobs/{job_id}", data=content, content_type="application/pdf")
        assert response.status_code == 200, response.data
        assert response.json["total"] == 2
        params = {"min_line_width_ratio": 0.16, "max_line_height": 10,
                  "min_rect_area_ratio": 0.001, "max_rect_area_ratio": 0.5}
        result = client.post(f"/jobs/{job_id}/pages/1", json=params)
        assert result.status_code == 200, result.data
        assert result.json["pages"][0]["horizontal_lines"][0]["width"] > 900
        image = client.get(f"/jobs/{job_id}/pages/1/image")
        assert image.status_code == 200
        assert image.data.startswith(b"\xff\xd8")
        blank = client.post(f"/jobs/{job_id}/pages/2", json=params)
        assert blank.status_code == 200
        assert blank.json["pages"][0]["page"] == 2
        assert "horizontal_lines" not in blank.json["pages"][0]
        assert client.delete(f"/jobs/{job_id}").status_code == 204
        assert client.post(f"/jobs/{job_id}/pages/1", json=params).status_code == 404
    finally:
        client.delete(f"/jobs/{job_id}")


@pytest.mark.parametrize("source", [b"%PDF-invalid", "oversized", "encrypted", "too_many_pages"])
def test_rejected_sources_leave_no_engine_cache(source):
    job_id = str(uuid4())
    if isinstance(source, str):
        with fitz.open() as document:
            document.new_page(width=10000 if source == "oversized" else 600,
                              height=10000 if source == "oversized" else 800)
            if source == "too_many_pages":
                for _ in range(1000):
                    document.new_page(width=10, height=10)
            source = document.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256,
                                     owner_pw="owner", user_pw="user") if source == "encrypted" else document.tobytes()
    result = app.test_client().put(f"/jobs/{job_id}", data=source, content_type="application/pdf")
    assert result.status_code == 422
    assert not job_dir(job_id).exists()


def test_timeout_kills_native_process_and_cleans_upload(monkeypatch):
    import multiprocessing
    from multiprocessing.process import BaseProcess

    real_join = BaseProcess.join

    def accelerated_join(process, timeout=None):
        # Accelerate the deadline, while still spawning/terminating/joining a real OS child.
        return real_join(process, 0.001 if timeout == 65 else timeout)

    monkeypatch.setattr(BaseProcess, "join", accelerated_join)
    previous = {child.pid for child in multiprocessing.active_children()}
    job_id = str(uuid4())
    with fitz.open() as document:
        document.new_page()
        response = app.test_client().put(f"/jobs/{job_id}", data=document.tobytes(),
                                         content_type="application/pdf")
    assert response.status_code == 504
    assert "exceeded 65 seconds" in response.json["error"]
    assert not job_dir(job_id).exists()
    assert {child.pid for child in multiprocessing.active_children()} == previous


def test_cancellation_releases_a_waiting_native_request():
    import threading
    import time
    from server import PROCESSING

    job_id = str(uuid4())
    with fitz.open() as document:
        document.new_page()
        content = document.tobytes()
    responses = []
    thread = threading.Thread(target=lambda: responses.append(
        app.test_client().put(f"/jobs/{job_id}", data=content, content_type="application/pdf")))
    PROCESSING.acquire()
    try:
        thread.start()
        deadline = time.monotonic() + 2
        while not (job_dir(job_id) / "source.pdf").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (job_dir(job_id) / "source.pdf").exists()
        assert app.test_client().delete(f"/jobs/{job_id}").status_code == 204
        thread.join(1)
        assert not thread.is_alive()
        assert responses[0].status_code == 422
        assert responses[0].json["error"] == "Job cancelled."
        assert not job_dir(job_id).exists()
    finally:
        PROCESSING.release()
        thread.join(5)
        app.test_client().delete(f"/jobs/{job_id}")


def test_release_version_reaches_cli_and_service_from_any_cwd(tmp_path):
    engine = tmp_path / "packages" / "engine"
    engine.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1]
    for name in ("skalu.py", "server.py"):
        shutil.copyfile(source / name, engine / name)
    (tmp_path / "package.json").write_text(json.dumps({"version": "9.8.7"}))
    cli = subprocess.check_output([sys.executable, str(engine / "skalu.py"), "--version"],
                                  cwd=tmp_path, text=True)
    assert cli.strip() == "skalu.py 9.8.7"
    health = subprocess.check_output(
        [sys.executable, "-c", "import server; print(server.app.test_client().get('/health').get_json()['version'])"],
        cwd=engine, text=True)
    assert health.strip() == "9.8.7"
