import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.exceptions import HTTPException
from .models import db


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, record):
    if connection.__class__.__module__.startswith("sqlite3"):
        connection.execute("PRAGMA foreign_keys=ON")


def create_app(config=None):
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    runtime = root / ".runtime"
    runtime.mkdir(exist_ok=True)
    app = Flask(__name__, static_folder=None)
    
    # Primary database is PostgreSQL per specification. Falls back to DATABASE_URL if configured.
    default_db_url = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/onecase")
    
    engine_options = {"connect_args": {"connect_timeout": 3}} if default_db_url.startswith("postgresql") else {}

    app.config.update(
        SQLALCHEMY_DATABASE_URI=default_db_url,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        STORAGE_PATH=str(runtime / "documents"),
        COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        SECRET_KEY=os.getenv("SECRET_KEY", "onecase-production-secret-key-32-bytes-secure"),
        MODEL_PATH=os.getenv("MODEL_PATH", str(root / ".runtime" / "models")),
        FRONTEND_PATH=str(root / "frontend" / "dist"),
    )

    app.config.update(config or {})
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}
    Path(app.config["STORAGE_PATH"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    Migrate(app, db)
    from .api import api
    from .cli import register
    app.register_blueprint(api, url_prefix="/api")
    register(app)

    @app.before_request
    def same_origin_writes():
        from flask import request, abort
        if request.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                abort(403, description="Cross-origin write requests are not permitted.")
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                abort(403, description="Cross-site write requests are not permitted.")

    @app.errorhandler(OperationalError)
    def db_operational_error(error):
        db.session.rollback()
        return jsonify(error={
            "message": "Primary database (PostgreSQL) is unavailable. Please verify that PostgreSQL is running and accessible at DATABASE_URL.",
            "status": 503
        }), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        db.session.rollback()
        return jsonify(error={"message": error.description, "status": error.code}), error.code

    @app.errorhandler(StaleDataError)
    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error={"message": "A concurrent request changed this record. Refresh and try again.", "status": 409}), 409

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        if request_is_api():
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok", "service": "onecase", "database": "connected"}
        except Exception as err:
            return jsonify({
                "status": "degraded",
                "service": "onecase",
                "database": "unavailable",
                "message": f"Primary database connection failed: {str(err)[:200]}"
            }), 503

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path):
        from flask import abort
        if path.startswith("api/"):
            abort(404)
        dist = Path(app.config["FRONTEND_PATH"])
        if path and (dist / path).is_file():
            return send_from_directory(dist, path)
        if not (dist / "index.html").exists():
            return {"message": "Run the frontend dev server or build frontend/dist."}, 404
        return send_from_directory(dist, "index.html")

    return app


def request_is_api():
    from flask import request
    return request.path.startswith("/api/")
