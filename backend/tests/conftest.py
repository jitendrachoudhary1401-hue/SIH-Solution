import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import db
from app.cli import seed_demo


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.db").as_posix(), "STORAGE_PATH": str(tmp_path / "documents"), "STORAGE_BACKEND": "local", "RATELIMIT_ENABLED": False})
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
