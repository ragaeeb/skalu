"""Version endpoint."""
from flask import Blueprint, current_app, jsonify, request

from ..extensions import limiter

version_bp = Blueprint("version", __name__)


@version_bp.get("/version")
@limiter.exempt
def version() -> tuple:
    settings = current_app.config["SETTINGS"]
    frontend_version = request.headers.get("X-Frontend-Version") or request.args.get("frontend_version")
    return (
        jsonify(
            {
                "backend_version": settings.app_version,
                "frontend_version": frontend_version,
                "git_sha": settings.git_sha,
                "build_time": settings.build_time,
            }
        ),
        200,
    )
