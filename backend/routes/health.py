"""Health route."""
from flask import Blueprint, jsonify

from ..extensions import limiter

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
@limiter.exempt
def health() -> tuple:
    return jsonify({"status": "ok"}), 200
