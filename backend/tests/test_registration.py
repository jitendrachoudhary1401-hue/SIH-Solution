import pytest
from sqlalchemy import select, func
from conftest import login
from app.models import db, User, Complaint, Grant, PermissionGrant, RoleAssignment, Notification
from app.api import hasher


def payload(kind="student", email="new.account@example.com"):
    return {"name": "New Account", "email": email, "password": "PersonalPassphrase!2026",
            "confirm_password": "PersonalPassphrase!2026", "account_type": kind, "organization": "Example institution"}


@pytest.mark.parametrize("kind", ["student", "parent", "faculty", "staff", "other"])
def test_public_registration_persists_and_starts_empty(app, client, kind):
    with app.app_context():
        before = db.session.scalar(select(func.count()).select_from(Complaint))
    result = client.post("/api/auth/register", json=payload(kind))
    assert result.status_code == 201
    assert result.json["approval_pending"] is False
    auth = client.post("/api/auth/login", json={"email": "new.account@example.com", "password": "PersonalPassphrase!2026"})
    assert auth.status_code == 200
    assert auth.json["user"]["role"] == kind
    assert auth.json["user"]["bureau_id"] is None
    assert auth.json["user"]["capabilities"] == {"account": True, "cases": True, "alerts": True}
    assert client.get("/api/account/summary").json == {"total": 0, "active": 0, "closed": 0, "unread_alerts": 0}
    assert client.get("/api/complaints").json["items"] == []
    assert client.get("/api/complaints/1").status_code == 404
    assert client.get("/api/admin/workspace").status_code == 403
    assert client.get("/api/directory").json["participants"] == []
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "new.account@example.com"))
        assert user.requested_role == kind
        assert hasher.verify(user.password_hash, "PersonalPassphrase!2026")
        assert user.password_hash != "PersonalPassphrase!2026"
        for model in (Grant, PermissionGrant, RoleAssignment, Notification):
            assert db.session.scalar(select(func.count()).select_from(model).where(model.user_id == user.id)) == 0
        assert db.session.scalar(select(func.count()).select_from(Complaint)) == before
    headers = {"X-CSRF-Token": auth.json["csrf"]}
    assert client.post("/api/auth/logout", json={}, headers=headers).status_code == 200
    assert client.post("/api/auth/login", json={"email": "NEW.ACCOUNT@example.com", "password": "PersonalPassphrase!2026"}).status_code == 200
    assert client.get("/api/account/summary").json["total"] == 0


@pytest.mark.parametrize("kind", ["officer", "lead", "reviewer", "committee", "verifier", "executive", "auditor", "admin"])
def test_staff_signup_does_not_grant_requested_privilege(app, client, kind):
    assert client.post("/api/auth/register", json=payload(kind)).status_code == 201
    auth = client.post("/api/auth/login", json={"email": "new.account@example.com", "password": "PersonalPassphrase!2026"})
    assert auth.status_code == 200
    user = auth.json["user"]
    assert user["approval_pending"] and user["role"] == "pending"
    assert user["requested_role"] == kind and user["roles"] == [] and user["bureau_id"] is None
    assert client.get("/api/account/summary").json == {"total": 0, "active": 0, "closed": 0, "unread_alerts": 0}
    for path in ("/api/admin/workspace", "/api/complaints", "/api/directory", "/api/operations"):
        assert client.get(path).status_code == 403


def test_admin_can_approve_a_saved_staff_request(app, client):
    assert client.post("/api/auth/register", json=payload("officer")).status_code == 201
    headers = login(client, "admin@onecase.demo")
    user = next(u for u in client.get("/api/admin/workspace").json["users"] if u["email"] == "new.account@example.com")
    assert user["approval_pending"] and user["requested_role"] == "officer"
    response = client.patch(f"/api/admin/users/{user['id']}", headers=headers,
                            json={"role": "officer", "bureau_id": 1, "approval_reference": "APPROVAL-2026-001", "reason": "Verified staff appointment"})
    assert response.status_code == 200
    auth = client.post("/api/auth/login", json={"email": "new.account@example.com", "password": "PersonalPassphrase!2026"})
    assert auth.status_code == 200
    assert auth.json["user"]["approval_pending"] is False
    assert auth.json["user"]["role"] == "officer"


def test_duplicate_email_is_case_insensitive(client):
    assert client.post("/api/auth/register", json=payload()).status_code == 201
    assert client.post("/api/auth/register", json=payload(email="NEW.ACCOUNT@example.com")).status_code == 409


@pytest.mark.parametrize("changes", [
    {"account_type": "superadmin"}, {"email": "invalid-email"},
    {"password": "short", "confirm_password": "short"}, {"confirm_password": "DifferentPassphrase!2026"},
    {"bureau_id": 1}, {"role": "admin"}, {"account_type": "officer", "organization": ""},
])
def test_invalid_signup_does_not_create_account(app, client, changes):
    data = payload()
    data.update(changes)
    assert client.post("/api/auth/register", json=data).status_code == 422
    with app.app_context():
        assert db.session.scalar(select(User).where(User.email == data["email"])) is None


def test_cross_origin_signup_is_rejected(client):
    assert client.post("/api/auth/register", json=payload(), headers={"Origin": "https://untrusted.example"}).status_code == 403
