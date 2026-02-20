"""Flask app factory for the Skalu backend."""
from __future__ import annotations

import logging
import sys

from flask import Flask
from flask_compress import Compress
from flask_cors import CORS

from .config import load_settings
from .extensions import limiter
from .routes.analyze import analyze_bp
from .routes.frontend import frontend_bp
from .routes.health import health_bp
from .routes.version import version_bp


def create_app() -> Flask:
    settings = load_settings()

    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format='{"severity":"%(levelname)s","message":"%(message)s","logger":"%(name)s"}',
    )

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "skalu-api"
    app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length
    app.config["SETTINGS"] = settings

    raw_origins = settings.allowed_origins
    origins = [origin.strip() for origin in raw_origins.split(",")] if raw_origins != "*" else "*"
    CORS(app, origins=origins, supports_credentials=False)
    Compress(app)

    limiter.init_app(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(version_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(frontend_bp)

    return app
