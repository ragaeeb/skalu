"""Application settings and environment parsing."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import tomllib

from demo_utils import DEFAULT_PARAMS


@dataclass(frozen=True)
class Settings:
    port: int
    allowed_origins: str
    max_content_length: int
    analyze_timeout_seconds: int
    stream_heartbeat_seconds: int
    log_level: str
    app_version: str
    git_sha: str
    build_time: str
    flask_debug: bool


DEFAULT_BACKEND_VERSION = "0.1.0"


def _load_backend_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject_path.exists():
        return DEFAULT_BACKEND_VERSION

    try:
        with pyproject_path.open("rb") as fh:
            data = tomllib.load(fh)
        return str(data.get("project", {}).get("version") or DEFAULT_BACKEND_VERSION)
    except OSError:
        return DEFAULT_BACKEND_VERSION


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    value = os.environ.get(name)
    result = default
    if value is not None:
        try:
            result = int(value)
        except ValueError:
            result = default

    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def load_settings() -> Settings:
    backend_version = _load_backend_version()
    return Settings(
        port=_env_int("PORT", 8080, minimum=1),
        allowed_origins=os.environ.get("ALLOWED_ORIGINS", "*"),
        max_content_length=_env_int("MAX_CONTENT_LENGTH", 10 * 1024 * 1024, minimum=1024),
        analyze_timeout_seconds=_env_int("ANALYZE_TIMEOUT_SECONDS", 3300, minimum=1, maximum=3600),
        stream_heartbeat_seconds=_env_int("STREAM_HEARTBEAT_SECONDS", 15, minimum=1, maximum=60),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        app_version=os.environ.get("APP_VERSION", backend_version),
        git_sha=os.environ.get("GIT_SHA", "dev"),
        build_time=os.environ.get("BUILD_TIME", "unknown"),
        flask_debug=_env_bool("FLASK_DEBUG", False),
    )


DEFAULT_DETECTION_PARAMS = {
    "min_line_width_ratio": DEFAULT_PARAMS.get("min_line_width_ratio", 0.2),
    "max_line_height": DEFAULT_PARAMS.get("max_line_height", 10),
    "min_rect_area_ratio": DEFAULT_PARAMS.get("min_rect_area_ratio", 0.001),
    "max_rect_area_ratio": DEFAULT_PARAMS.get("max_rect_area_ratio", 0.5),
}
