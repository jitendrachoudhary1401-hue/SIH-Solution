import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.exceptions import HTTPException
from .models import db


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, record):
    if connection.__class__.__module__.startswith("sqlite3"):
        connection.execute("PRAGMA foreign_keys=ON")


def create_app(config=None):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    root = Path(__file__).resolve().parents[2]
    runtime = root / ".runtime"
    runtime.mkdir(exist_ok=True)
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///" + (runtime / "onecase.db").as_posix()),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        STORAGE_PATH=os.getenv("STORAGE_PATH", str(runtime / "documents")),
        COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        MODEL_PATH=os.getenv("MODEL_PATH", str(root / ".runtime" / "models")),
        FRONTEND_PATH=str(root / "frontend" / "dist"),
        SECRET_KEY=os.getenv("SECRET_KEY"),
        APP_ENV=os.getenv("APP_ENV", "development"),
        MFA_ENCRYPTION_KEY=os.getenv("MFA_ENCRYPTION_KEY", ""),
        SESSION_IDLE_MINUTES=int(os.getenv("SESSION_IDLE_MINUTES", "30")),
        STEP_UP_MINUTES=int(os.getenv("STEP_UP_MINUTES", "10")),
        CLAMAV_HOST=os.getenv("CLAMAV_HOST", ""),
        CLAMAV_PORT=int(os.getenv("CLAMAV_PORT", "3310")),
        DOCUMENT_LIMIT_PER_CASE=int(os.getenv("DOCUMENT_LIMIT_PER_CASE", "30")),
        JOB_LIMIT_PER_HOUR=int(os.getenv("JOB_LIMIT_PER_HOUR", "30")),
        SECURITY_CONTACT=os.getenv("SECURITY_CONTACT", "Local demonstration administrator"),
    )
    app.config.update(config or {})
    if app.config["APP_ENV"] == "production" and (not app.config["COOKIE_SECURE"] or not app.config["SECRET_KEY"] or not app.config["MFA_ENCRYPTION_KEY"]):
        raise RuntimeError("Production requires secure HTTPS cookies, SECRET_KEY and MFA_ENCRYPTION_KEY.")
    Path(app.config["STORAGE_PATH"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    Migrate(app, db)
    from .api import api
    from .cli import register
    from .workflow import workflow_api
    from .administration import administration_api
    from .security import security_api
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(workflow_api, url_prefix="/api")
    app.register_blueprint(administration_api, url_prefix="/api")
    app.register_blueprint(security_api, url_prefix="/api")
    register(app)

    @app.before_request
    def same_origin_writes():
        from flask import request, abort, g
        from uuid import uuid4
        g.request_id = uuid4().hex
        if request.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                abort(403, description="Cross-origin write requests are not permitted.")
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                abort(403, description="Cross-site write requests are not permitted.")

    @app.errorhandler(HTTPException)
    def http_error(error):
        db.session.rollback()
        from flask import g
        from .models import ActionEvent
        if error.code in (403, 409, 422) and getattr(g, "user", None):
            db.session.add(ActionEvent(actor_id=g.user.id, actor_name=g.user.name, bureau_id=g.user.bureau_id,
                                      kind="request_rejected", summary="A write request was rejected", reason="Request validation or authorization did not pass.",
                                      outcome="denied" if error.code == 403 else "failed", severity="warning"))
            db.session.commit()
        return jsonify(error={"message": error.description, "status": error.code, "request_id": getattr(g, "request_id", "")}), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        from flask import g
        db.session.rollback()
        app.logger.error("Unhandled request failure %s (%s)", getattr(g, "request_id", ""), type(error).__name__)
        return jsonify(error={"message": "The request could not be completed. Contact the administrator with this request ID.", "status": 500, "request_id": getattr(g, "request_id", "")}), 500

    @app.errorhandler(StaleDataError)
    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error={"message": "A concurrent request changed this record. Refresh and try again.", "status": 409}), 409

    @app.after_request
    def security_headers(response):
        from flask import g
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if app.config["APP_ENV"] == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        if request_is_api():
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "service": "onecase"}

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
