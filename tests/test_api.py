from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend import create_app
from backend.errors import AnalysisTimeoutError


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def _multipart(extra: dict | None = None) -> dict:
    payload = {
        "file": (io.BytesIO(b"%PDF-1.4 fake"), "sample.pdf"),
        "include_empty_pages": "true",
        "include_visualizations": "false",
        "stream": "false",
        "min_line_width_ratio": "0.2",
        "max_line_height": "10",
        "min_rect_area_ratio": "0.001",
        "max_rect_area_ratio": "0.5",
    }
    if extra:
        payload.update(extra)
    return payload


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_version(client):
    response = client.get("/version", headers={"X-Frontend-Version": "0.1.0+dev"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["backend_version"]
    assert payload["frontend_version"] == "0.1.0+dev"
    assert "git_sha" in payload
    assert "build_time" in payload


def test_analyze_non_stream_success(client, monkeypatch):
    expected = {
        "result_json": "{\"pages\":[]}",
        "result_data": {"pages": []},
        "summary": {"type": "pdf", "pages": []},
        "processed_filename": "sample.pdf",
        "detection_params": {
            "min_line_width_ratio": 0.2,
            "max_line_height": 10,
            "min_rect_area_ratio": 0.001,
            "max_rect_area_ratio": 0.5,
        },
        "visualizations": [],
        "debug_groups": [],
    }

    def fake_run_analysis_with_timeout(workdir, filename, options, timeout_seconds):
        assert filename == "sample.pdf"
        assert options.include_visualizations is False
        assert options.include_empty_pages is True
        assert timeout_seconds > 0
        return expected

    monkeypatch.setattr("backend.routes.analyze.run_analysis_with_timeout", fake_run_analysis_with_timeout)

    response = client.post("/analyze", data=_multipart(), content_type="multipart/form-data")

    assert response.status_code == 200
    assert response.get_json()["processed_filename"] == "sample.pdf"


def test_analyze_non_stream_timeout(client, monkeypatch):
    def fake_run_analysis_with_timeout(workdir, filename, options, timeout_seconds):
        raise AnalysisTimeoutError("timed out")

    monkeypatch.setattr("backend.routes.analyze.run_analysis_with_timeout", fake_run_analysis_with_timeout)

    response = client.post("/analyze", data=_multipart(), content_type="multipart/form-data")
    payload = response.get_json()

    assert response.status_code == 504
    assert payload == {"error": "timed out", "code": "timeout"}


def test_analyze_stream_success_event_order(client, monkeypatch):
    events = [
        {"type": "accepted", "filename": "sample.pdf", "started_at": "2026-02-19T00:00:00Z"},
        {"type": "progress", "processed": 1, "total": 2, "message": "Processing page 2 of 2"},
        {
            "type": "result",
            "payload": {
                "result_json": "{\"pages\":[]}",
                "result_data": {"pages": []},
                "summary": {"type": "pdf", "pages": []},
                "processed_filename": "sample.pdf",
                "detection_params": {
                    "min_line_width_ratio": 0.2,
                    "max_line_height": 10,
                    "min_rect_area_ratio": 0.001,
                    "max_rect_area_ratio": 0.5,
                },
                "visualizations": [],
                "debug_groups": [],
            },
        },
    ]

    def fake_stream_analysis_events(workdir, filename, options, timeout_seconds, heartbeat_seconds):
        assert filename == "sample.pdf"
        assert options.stream is True
        assert timeout_seconds > 0
        assert heartbeat_seconds > 0
        yield from events

    monkeypatch.setattr("backend.routes.analyze.stream_analysis_events", fake_stream_analysis_events)

    response = client.post(
        "/analyze",
        data=_multipart({"stream": "true"}),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.mimetype == "application/x-ndjson"

    lines = [line for line in response.get_data(as_text=True).splitlines() if line.strip()]
    decoded = [json.loads(line) for line in lines]
    assert [event["type"] for event in decoded] == ["accepted", "progress", "result"]


def test_analyze_stream_timeout_event(client, monkeypatch):
    def fake_stream_analysis_events(workdir, filename, options, timeout_seconds, heartbeat_seconds):
        yield {"type": "accepted", "filename": "sample.pdf", "started_at": "2026-02-19T00:00:00Z"}
        yield {"type": "error", "code": "timeout", "message": "timed out"}

    monkeypatch.setattr("backend.routes.analyze.stream_analysis_events", fake_stream_analysis_events)

    response = client.post(
        "/analyze",
        data=_multipart({"stream": "true"}),
        content_type="multipart/form-data",
    )
    lines = [line for line in response.get_data(as_text=True).splitlines() if line.strip()]
    decoded = [json.loads(line) for line in lines]

    assert decoded[-1]["type"] == "error"
    assert decoded[-1]["code"] == "timeout"


def test_analyze_invalid_params_returns_bad_input(client):
    response = client.post(
        "/analyze",
        data=_multipart({"max_line_height": "not-a-number"}),
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "bad_input"


def test_analyze_invalid_file_type_returns_bad_input(client):
    response = client.post(
        "/analyze",
        data={
            "file": (io.BytesIO(b"plain text"), "sample.txt"),
        },
        content_type="multipart/form-data",
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["code"] == "bad_input"
