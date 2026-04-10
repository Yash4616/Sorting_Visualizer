from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_compress import Compress
from werkzeug.exceptions import HTTPException

from backend.api import create_api_blueprint
from backend.run_manager import SortRunManager


def create_app(config: dict[str, Any] | None = None) -> Flask:
    project_root = Path(__file__).resolve().parent.parent
    dist_dir = project_root / "frontend" / "dist"

    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        DEBUG=False,
        SERVE_FRONTEND=True,
        JSON_SORT_KEYS=False,
        COMPRESS_MIN_SIZE=1024,
    )
    if config:
        app.config.update(config)

    app.config["JSON_SORT_KEYS"] = False
    Compress(app)

    if bool(app.config.get("DEBUG", False)):
        CORS(
            app,
            resources={r"/api/*": {"origins": ["http://localhost:5173"]}},
            supports_credentials=False,
        )

    run_manager = SortRunManager()
    app.register_blueprint(create_api_blueprint(run_manager))

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return jsonify({"error": exc.description}), exc.code

    @app.errorhandler(Exception)
    def handle_uncaught_exception(_: Exception):
        return jsonify({"error": "internal server error"}), 500

    serve_frontend = bool(app.config.get("SERVE_FRONTEND", not bool(app.config.get("DEBUG", False))))

    @app.get("/")
    def index():
        if not serve_frontend:
            return jsonify({"status": "backend-ready", "frontend": "served-by-vite-dev-server"}), 200

        index_file = dist_dir / "index.html"
        if index_file.exists():
            return send_from_directory(str(dist_dir), "index.html")

        return jsonify({"error": "frontend build not found"}), 503

    @app.get("/<path:path>")
    def static_proxy(path: str):
        if not serve_frontend:
            return jsonify({"error": "not found"}), 404

        file_path = dist_dir / path
        if file_path.exists() and file_path.is_file():
            return send_from_directory(str(dist_dir), path)

        index_file = dist_dir / "index.html"
        if index_file.exists():
            return send_from_directory(str(dist_dir), "index.html")

        return jsonify({"error": "not found"}), 404

    return app
