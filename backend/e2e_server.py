"""Disposable synthetic database for browser tests; never touches the user's demo DB."""
import tempfile
import os
import json
from pathlib import Path
from waitress import serve
from app import create_app
from app.models import db
from app.cli import seed_demo
from app.jobs import monitor

with tempfile.TemporaryDirectory(prefix="onecase-e2e-") as directory:
    root = Path(directory)
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (root / "test.db").as_posix(), "STORAGE_PATH": str(root / "documents"), "STORAGE_BACKEND": "local", "RATELIMIT_ENABLED": False})
    # Capture provider requests only in this disposable test host. Runtime
    # main.py/serve.py never import this fixture or expose a mailbox endpoint.
    from app import mail
    app.config.update(SENDGRID_API_KEY="isolated-browser-test-key", SENDGRID_FROM_EMAIL="test@example.test",
                      SENDGRID_FROM_NAME="OneCase", PUBLIC_APP_URL="http://127.0.0.1:5174")
    outbox = []
    class AcceptedEmail:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class CaptureSendGrid:
        def open(self, request, **kwargs):
            assert request.full_url == "https://api.sendgrid.com/v3/mail/send"
            outbox.append(json.loads(request.data))
            return AcceptedEmail()
    mail.build_opener = lambda *args: CaptureSendGrid()
    @app.get("/api/test-only/mailbox")
    def test_mailbox():
        from flask import request
        email = request.args.get("email", "")
        return {"items": [item for item in outbox if item["personalizations"][0]["to"][0]["email"] == email]}
    @app.post('/api/test-only/reset-auth-attempts')
    def reset_auth_attempts():
        # This disposable loopback host is never imported by main.py/serve.py.
        # Each browser scenario starts with independent brute-force counters.
        from flask import request, abort
        from sqlalchemy import delete
        from app.models import LoginAttempt
        if request.get_json(silent=True) != {'fixture': 'isolated-browser-test'}:
            abort(403)
        db.session.execute(delete(LoginAttempt))
        db.session.commit()
        return {'ok': True}
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
        from app.demo import seed_public_demo_accounts
        seed_public_demo_accounts()
        app.config["DEMO_ACCOUNTS_ENABLED"] = True
        monitor()
        if os.getenv("E2E_MATCHING") == "1":
            from app.matching import process
            process(1, 1)
    serve(app, host="127.0.0.1", port=5051)
