"""Frontend SPA static asset routes for Cloud Run runtime."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, send_from_directory

frontend_bp = Blueprint("frontend", __name__)


def _dist_dir() -> Path:
    return Path(current_app.root_path).parent / "frontend" / "dist"


@frontend_bp.get("/")
def index():
    dist_dir = _dist_dir()
    index_path = dist_dir / "index.html"
    if not index_path.exists():
        return {"error": "Frontend build not found. Run frontend build or use Vite dev server."}, 404
    return send_from_directory(dist_dir, "index.html")


@frontend_bp.get("/<path:path>")
def serve_spa(path: str):
    dist_dir = _dist_dir()
    file_path = dist_dir / path
    if file_path.exists() and file_path.is_file():
        return send_from_directory(dist_dir, path)

    index_path = dist_dir / "index.html"
    if not index_path.exists():
        return {"error": "Frontend build not found. Run frontend build or use Vite dev server."}, 404
    return send_from_directory(dist_dir, "index.html")
