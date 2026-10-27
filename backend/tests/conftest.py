import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import db
from app.cli import seed_demo


@pytest.fixture
def app(tmp_path):
    from cryptography.fernet import Fernet
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.db").as_posix(), "STORAGE_PATH": str(tmp_path / "documents"), "STORAGE_BACKEND": "local", "RATELIMIT_ENABLED": False, "MFA_ENCRYPTION_KEY": Fernet.generate_key().decode()})
    app.config.update(SENDGRID_API_KEY="", SENDGRID_FROM_EMAIL="")
    with app.app_context():
        db.create_all()
        seed_demo("TestPassword!2026")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="lead.rb@onecase.demo"):
    response = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["csrf"]}


def approved_test_evidence(app, case_id=1):
    """A pre-approved synthetic fixture, not an upload scanner bypass in the app."""
    from app.models import Attachment
    from app import storage
    from pypdf import PdfWriter
    import io, hashlib
    from uuid import uuid4
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    content = output.getvalue()
    with app.app_context():
        key = uuid4().hex
        backend, bucket = storage.put(key, content, "application/pdf")
        item = Attachment(complaint_id=case_id, filename="approved-synthetic-outcome.pdf", key=key,
                          media_type="application/pdf", size=len(content), checksum=hashlib.sha256(content).hexdigest(),
                          scan_state="clean", scan_detail="Pre-approved synthetic test fixture", storage_backend=backend, storage_bucket=bucket)
        db.session.add(item)
        db.session.commit()
        return item.id
