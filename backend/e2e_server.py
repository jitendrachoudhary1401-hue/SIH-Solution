"""Disposable synthetic database for browser tests; never touches the user's demo DB."""
import tempfile
import os
from pathlib import Path
from waitress import serve
from app import create_app
from app.models import db
from app.cli import seed_demo
from app.jobs import monitor

with tempfile.TemporaryDirectory(prefix="onecase-e2e-") as directory:
    root = Path(directory)
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (root / "test.db").as_posix(), "STORAGE_PATH": str(root / "documents"), "STORAGE_BACKEND": "local", "RATELIMIT_ENABLED": False})
    # This disposable test host validates actual file structure and injects a
    # scanner double. Production never installs this synthetic scanner.
    from app import documents
    documents.scan_file = lambda path: ("clean", "Isolated browser-test scanner fixture")
    @app.after_request
    def scan_test_upload(response):
        from flask import request
        if request.path.endswith("/attachments") and request.method == "POST" and response.status_code == 201:
            documents.scan_pending()
        return response
    with app.app_context():
        db.create_all()
        seed_demo("OneCaseDemo!2026")
        monitor()
        if os.getenv("E2E_MATCHING") == "1":
            from app.matching import process
            process(1, 1)
    serve(app, host="127.0.0.1", port=5051)
