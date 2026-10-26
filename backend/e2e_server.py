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
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///" + (root / "test.db").as_posix(), "STORAGE_PATH": str(root / "documents")})
    with app.app_context():
        db.create_all()
        seed_demo("OneCaseDemo!2026")
        monitor()
        if os.getenv("E2E_MATCHING") == "1":
            from app.matching import process
            process(1, 1)
    serve(app, host="127.0.0.1", port=5051)
