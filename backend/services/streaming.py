"""NDJSON streaming helpers for single-shot analysis."""
from __future__ import annotations

import json
import multiprocessing as mp
from multiprocessing.connection import Connection
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Iterator

from demo_utils import job_progress_message

from ..errors import AnalysisTimeoutError, ProcessingError
from ..models import AnalyzeOptions
from .analysis import run_analysis


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _worker(conn: Connection, workdir: str, filename: str, options_data: dict) -> None:
    options = AnalyzeOptions.from_dict(options_data)
    suffix = Path(filename).suffix.lower()

    def progress_callback(done: int, total: int) -> None:
        conn.send(
            {
                "type": "progress",
                "processed": done,
                "total": total,
                "message": job_progress_message(done, total, suffix),
            }
        )

    try:
        payload = run_analysis(workdir, filename, options, progress_callback=progress_callback)
        conn.send({"type": "result", "payload": payload})
    except Exception as exc:  # pylint: disable=broad-except
        conn.send({"type": "error", "code": "processing_error", "message": str(exc)})
    finally:
        conn.close()


def _start_analysis_process(workdir: str, filename: str, options: AnalyzeOptions) -> tuple[mp.Process, Connection]:
    ctx = mp.get_context("spawn")
    recv_conn, send_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_worker,
        args=(send_conn, workdir, filename, options.to_dict()),
        daemon=True,
    )
    process.start()
    send_conn.close()
    return process, recv_conn


def _cleanup_process(process: mp.Process, recv_conn: Connection) -> None:
    try:
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
    finally:
        recv_conn.close()


def _next_event_or_none(process: mp.Process, recv_conn: Connection, wait_seconds: float) -> dict | None:
    if recv_conn.poll(max(0.0, wait_seconds)):
        try:
            return recv_conn.recv()
        except EOFError:
            return None

    if not process.is_alive():
        return None

    return None


def run_analysis_with_timeout(workdir: str, filename: str, options: AnalyzeOptions, timeout_seconds: int) -> dict:
    process, recv_conn = _start_analysis_process(workdir, filename, options)
    started = monotonic()

    try:
        while True:
            elapsed = monotonic() - started
            if elapsed >= timeout_seconds:
                raise AnalysisTimeoutError(
                    f"Analysis exceeded {timeout_seconds} seconds. Reduce file size/settings and retry."
                )

            event = _next_event_or_none(process, recv_conn, 0.5)
            if event is None:
                if not process.is_alive():
                    if process.exitcode and process.exitcode != 0:
                        raise ProcessingError("Analysis worker exited unexpectedly")
                    raise ProcessingError("Analysis worker exited without a terminal result event")
                continue

            event_type = event.get("type")
            if event_type == "result":
                return event["payload"]
            if event_type == "error":
                code = event.get("code", "processing_error")
                message = event.get("message", "Processing failed")
                if code == "timeout":
                    raise AnalysisTimeoutError(message)
                raise ProcessingError(message)
    finally:
        _cleanup_process(process, recv_conn)


def stream_analysis_events(
    workdir: str,
    filename: str,
    options: AnalyzeOptions,
    timeout_seconds: int,
    heartbeat_seconds: int,
) -> Iterator[dict]:
    process, recv_conn = _start_analysis_process(workdir, filename, options)
    started = monotonic()

    try:
        yield {"type": "accepted", "filename": filename, "started_at": _now_iso()}

        while True:
            elapsed = monotonic() - started
            if elapsed >= timeout_seconds:
                yield {
                    "type": "error",
                    "code": "timeout",
                    "message": f"Analysis exceeded {timeout_seconds} seconds. Reduce file size/settings and retry.",
                }
                break

            wait_timeout = max(0.1, min(float(heartbeat_seconds), float(timeout_seconds - elapsed)))
            event = _next_event_or_none(process, recv_conn, wait_timeout)
            if event is None:
                if not process.is_alive():
                    if process.exitcode and process.exitcode != 0:
                        yield {
                            "type": "error",
                            "code": "processing_error",
                            "message": "Analysis worker exited unexpectedly",
                        }
                    else:
                        yield {
                            "type": "error",
                            "code": "processing_error",
                            "message": "Analysis worker exited without a terminal result event",
                        }
                    break

                yield {"type": "heartbeat", "ts": _now_iso()}
                continue

            yield event
            if event.get("type") in {"result", "error"}:
                break
    finally:
        _cleanup_process(process, recv_conn)


def encode_event_line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"
