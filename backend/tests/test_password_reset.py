from datetime import timedelta
import json
from urllib.parse import urlsplit, parse_qs
import pytest
from sqlalchemy import select, func
from app.models import db, User, PasswordReset, Session, now
from app.auth import digest
from app.password_reset import issue_token
from app import mail, password_reset
from conftest import login


@pytest.fixture
def sendgrid(app, monkeypatch):
    app.config.update(SENDGRID_API_KEY="private-test-key", SENDGRID_FROM_EMAIL="sender@example.test", SENDGRID_FROM_NAME="OneCase")
    calls, messages = [], []
    class Response:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Opener:
        def open(self, request, **kwargs):
            calls.append(request)
            messages.append(json.loads(request.data))
            return Response()
    class Thread:
        def __init__(self, target, args, **kwargs): self.target, self.args = target, args
        def start(self): self.target(*self.args)
    monkeypatch.setattr(mail, "build_opener", lambda *args: Opener())
    monkeypatch.setattr(password_reset, "Thread", Thread)
    return calls, messages


def token_for(app):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "lead.rb@onecase.demo"))
        token = issue_token(user)
        db.session.commit()
        return token


def replacement(token, **extra):
    return {"token": token, "password": "NewPrivatePassphrase!2026", "confirm_password": "NewPrivatePassphrase!2026", **extra}


def test_sendgrid_reset_links_are_single_use_and_revoke_sessions(app, client, sendgrid):
    calls, messages = sendgrid
    auth = client.post("/api/auth/login", json={"email": "lead.rb@onecase.demo", "password": "TestPassword!2026"})
    old_cookie = client.get_cookie("onecase_session").value
    other_token = token_for(app)
    known = client.post("/api/auth/forgot-password", json={"email": "LEAD.RB@onecase.demo"}, headers={"Host": "untrusted.example"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"})
    assert known.status_code == unknown.status_code == 202 and known.json == unknown.json
    assert len(messages) == 1 and messages[0]["personalizations"][0]["to"][0]["email"] == "lead.rb@onecase.demo"
    assert calls[0].full_url == "https://api.sendgrid.com/v3/mail/send"
    assert calls[0].get_header("Authorization") == "Bearer private-test-key"
    assert messages[0]["tracking_settings"]["click_tracking"]["enable"] is False
    link = next(line for line in messages[0]["content"][0]["value"].splitlines() if line.startswith("http"))
    assert link.startswith("http://127.0.0.1:5173/reset-password#token=")
    token = parse_qs(urlsplit(link).fragment)["token"][0]
    assert token not in str(known.json)
    with app.app_context():
        assert db.session.get(PasswordReset, digest(token)) is not None
        assert db.session.get(PasswordReset, token) is None
    response = client.post("/api/auth/reset-password", json=replacement(token))
    assert response.status_code == 200
    assert client.get_cookie("onecase_session") is None
    assert client.get("/api/auth/me").status_code == 401
    with app.app_context():
        assert db.session.get(Session, digest(old_cookie)) is None
    assert client.post("/api/auth/reset-password", json=replacement(token)).status_code == 422
    assert client.post("/api/auth/reset-password", json=replacement(other_token)).status_code == 422
    assert client.post("/api/auth/login", json={"email": "lead.rb@onecase.demo", "password": "TestPassword!2026"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "lead.rb@onecase.demo", "password": "NewPrivatePassphrase!2026"}).status_code == 200
    assert len(messages) == 2 and messages[1]["subject"] == "Your OneCase password was changed"


@pytest.mark.parametrize("condition", ["expired", "used", "disabled", "wrong"])
def test_invalid_link_cannot_change_password(app, client, condition):
    token = token_for(app)
    with app.app_context():
        reset = db.session.get(PasswordReset, digest(token))
        user = db.session.get(User, reset.user_id)
        old_hash = user.password_hash
        if condition == "expired": reset.expires_at = now() - timedelta(seconds=1)
        if condition == "used": reset.used_at = now()
        if condition == "disabled": user.active = False
        if condition == "wrong": token = "x" * 64
        user_id = user.id
        db.session.commit()
    assert client.post("/api/auth/reset-password", json=replacement(token)).status_code == 422
    with app.app_context(): assert db.session.get(User, user_id).password_hash == old_hash


def test_reset_requires_mfa_when_enabled_and_does_not_disable_it(app, client):
    token = token_for(app)
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "lead.rb@onecase.demo"))
        from app.security import cipher
        user.mfa_enabled = True
        user.mfa_secret = cipher().encrypt(b"JBSWY3DPEHPK3PXP").decode()
        user.recovery_codes = [digest("test-recovery-code")]
        db.session.commit()
    response = client.post("/api/auth/reset-password", json=replacement(token))
    assert response.status_code == 403 and response.json["error"]["mfa_required"]
    assert client.post("/api/auth/reset-password", json=replacement(token, verification_code="test-recovery-code")).status_code == 200
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "lead.rb@onecase.demo"))
        assert user.mfa_enabled is True and user.recovery_codes == []


def test_unconfigured_mail_and_password_validation_are_honest(app, client):
    app.config.update(SENDGRID_API_KEY="", SENDGRID_FROM_EMAIL="")
    assert client.post("/api/auth/forgot-password", json={"email": "lead.rb@onecase.demo"}).status_code == 503
    with app.app_context(): assert db.session.scalar(select(func.count()).select_from(PasswordReset)) == 0
    token = token_for(app)
    assert client.post("/api/auth/reset-password", json=replacement(token, confirm_password="AnotherPassphrase!2026")).status_code == 422
    assert client.post("/api/auth/reset-password", json=replacement(token, password="short", confirm_password="short")).status_code == 422


def test_failed_delivery_revokes_token(app, client, sendgrid, monkeypatch):
    def fail(*args): raise OSError("SendGrid unavailable")
    monkeypatch.setattr(mail, "send_email", fail)
    assert client.post("/api/auth/forgot-password", json={"email": "lead.rb@onecase.demo"}).status_code == 202
    with app.app_context(): assert db.session.scalar(select(func.count()).select_from(PasswordReset)) == 0
