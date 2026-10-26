import io
from datetime import timedelta
from sqlalchemy import select, func
from conftest import login, approved_test_evidence
from app.models import db, now, Assignment, ActionEvent, Complaint, Notification, Session, Job, User
from app.jobs import monitor


def payload():
    return {"institution_id": 1, "owner_id": 1, "category": "Fee refund", "description": "The admission deposit has not been returned following a timely withdrawal.",
            "priority": "high", "received_at": (now() - timedelta(days=1)).isoformat(), "next_action": "Request refund acknowledgement"}


def test_access_csrf_expiry_logout(client, app):
    assert client.get("/api/complaints").status_code == 401
    headers = login(client)
    assert client.get("/api/complaints/2").status_code == 404  # PGRC restricted
    assert client.post("/api/complaints/1/actions", json={"version": 1, "reason": "Review recorded"}).status_code == 403
    assert client.post("/api/auth/logout", headers=headers, json={}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    headers = login(client)
    with app.app_context():
        session = db.session.scalar(select(Session))
        session.expires_at = now() - timedelta(seconds=1)
        db.session.commit()
    assert client.get("/api/complaints").status_code == 401


def test_registration_idempotency_validation_and_rollback(client, app):
    headers = {**login(client), "Idempotency-Key": "request-123456"}
    data = payload()
    response = client.post("/api/complaints", headers=headers, json=data)
    assert response.status_code == 201, response.json
    case = response.json
    replay = client.post("/api/complaints", headers=headers, json=data)
    assert replay.status_code == 200 and replay.json["id"] == case["id"]
    data["description"] += " Another issue."
    assert client.post("/api/complaints", headers=headers, json=data).status_code == 409
    assert client.post("/api/complaints", headers={**headers, "Idempotency-Key": "request-invalid"}, json={**data, "owner_id": 3}).status_code == 422
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Complaint)) == 9
        assert db.session.scalar(select(func.count()).select_from(Assignment).where(Assignment.complaint_id == case["id"])) == 1
        assert db.session.scalar(select(func.count()).select_from(ActionEvent).where(ActionEvent.complaint_id == case["id"])) == 1
        assert db.session.scalar(select(Job).where(Job.complaint_id == case["id"]))


def test_lifecycle_stale_version_and_reporting(client, app):
    headers = login(client)
    first = client.get("/api/complaints/1").json
    bad = client.post("/api/complaints/1/status", headers=headers, json={"version": first["version"], "status": "received", "reason": "Invalid transition"})
    assert bad.status_code == 422
    document = approved_test_evidence(app)
    disposed = client.post("/api/complaints/1/status", headers=headers, json={"version": first["version"], "status": "disposed", "reason": "Documented resolution accepted", "outcome_document_id": document, "communication": "Synthetic outcome communicated to the complainant by recorded correspondence"})
    assert disposed.status_code == 200
    stale = client.post("/api/complaints/1/actions", headers=headers, json={"version": first["version"], "reason": "Stale action must fail"})
    assert stale.status_code == 409
    reopened = client.post("/api/complaints/1/status", headers=headers, json={"version": disposed.json["version"], "status": "under_review", "reason": "New evidence requires review"})
    assert reopened.status_code == 200
    summary = client.get("/api/dashboard/summary").json
    records = client.get("/api/complaints").json["items"]
    assert summary["total"] == len(records)
    assert summary["active"] == sum(c["status"] != "disposed" for c in records)
    assert summary["overdue"] == sum(c["deadline_condition"] == "overdue" for c in records)


def test_transfer_atomic_ownership_and_access(client, app):
    headers = login(client)
    version = client.get("/api/complaints/1").json["version"]
    invalid = client.post("/api/complaints/1/transfer", headers=headers, json={"version": version, "owner_id": 999, "reason": "A valid transfer reason"})
    assert invalid.status_code == 422
    response = client.post("/api/complaints/1/transfer", headers=headers, json={"version": version, "owner_id": 3, "reason": "PGRC to coordinate refund response"})
    assert response.status_code == 200
    assert client.get("/api/complaints/1").status_code == 404
    with app.app_context():
        assignments = db.session.scalars(select(Assignment).where(Assignment.complaint_id == 1)).all()
        assert len(assignments) == 2 and sum(a.ended_at is None for a in assignments) == 1
        assert db.session.get(Complaint, 1).owner_id == 3
    headers = login(client, "lead.pgrc@onecase.demo")
    assert client.get("/api/complaints/1").json["owner_id"] == 3
    assert client.post(f"/api/transfers/{response.json['id']}/acknowledge", headers=headers, json={}).status_code == 200


def test_attachments_protected_and_validated(client, app, monkeypatch):
    headers = login(client)
    version = str(client.get("/api/complaints/1").json["version"])
    invalid = client.post("/api/complaints/1/attachments", headers=headers, data={"version": version, "file": (io.BytesIO(b"<script>"), "bad.pdf")})
    assert invalid.status_code == 422
    uploaded = client.post("/api/complaints/1/attachments", headers=headers, data={"version": version, "file": (io.BytesIO(b"%PDF-1.4\nSynthetic test evidence"), "evidence.pdf")})
    assert uploaded.status_code == 201
    attachment = client.get("/api/complaints/1").json["attachments"][0]
    assert client.get(f"/api/attachments/{attachment['id']}/download").status_code == 423
    from app import documents
    monkeypatch.setattr(documents, "validate_file", lambda *args: None)
    monkeypatch.setattr(documents, "scan_file", lambda *args: ("clean", "Injected scanner test double"))
    with app.app_context():
        documents.scan_pending()
    assert client.get(f"/api/attachments/{attachment['id']}/download").status_code == 200
    login(client, "lead.pgrc@onecase.demo")
    assert client.get(f"/api/attachments/{attachment['id']}/download").status_code == 404


def test_monitoring_deduplicates_and_admin_has_no_case_access(client, app):
    with app.app_context():
        monitor()
        count = db.session.scalar(select(func.count()).select_from(Notification))
        monitor()
        assert db.session.scalar(select(func.count()).select_from(Notification)) == count and count > 0
    login(client, "admin@onecase.demo")
    assert client.get("/api/complaints").json["total"] == 0
    assert client.get("/api/dashboard/summary").json["total"] == 0
    assert client.get("/api/complaints/1").status_code == 404
    assert all(e["complaint_id"] is None for e in client.get("/api/audit-logs").json["items"])


def test_officer_cannot_edit_other_owner_or_transfer(client):
    headers = login(client, "officer.rb@onecase.demo")
    assert client.get("/api/complaints/1").status_code == 200
    assert client.post("/api/complaints/1/actions", headers=headers, json={"version": 1, "reason": "Attempted unauthorized edit"}).status_code == 403
    assert client.post("/api/complaints/3/transfer", headers=headers, json={"version": 1, "owner_id": 1, "reason": "Officer transfer attempt"}).status_code == 403


def test_filters_pagination_exports_and_refresh(client):
    headers = login(client)
    first = client.get("/api/complaints?limit=2").json
    second = client.get(f"/api/complaints?limit=2&cursor={first['nextCursor']}").json
    assert not {c["id"] for c in first["items"]} & {c["id"] for c in second["items"]}
    assert first["total"] == second["total"]
    assert client.get("/api/complaints?limit=bad").status_code == 422
    filtered = client.get("/api/complaints?overdue=true").json
    assert all(c["deadline_condition"] == "overdue" for c in filtered["items"])
    exported = client.get("/api/reports/complaints.csv?overdue=true")
    assert len(exported.text.strip().splitlines()) - 1 == filtered["total"]
    refreshed = client.post("/api/auth/refresh", headers=headers, json={})
    assert refreshed.status_code == 200 and refreshed.json["csrf"] != headers["X-CSRF-Token"]
    assert client.post("/api/auth/logout", headers=headers, json={}).status_code == 403


def test_cross_origin_and_rate_limit(client):
    assert client.post("/api/auth/login", headers={"Origin": "https://attacker.example"}, json={}).status_code == 403
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email": "nobody@example.test", "password": "incorrect"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@example.test", "password": "incorrect"}).status_code == 429


def test_sla_pause_resume(client):
    headers = login(client)
    c = client.get("/api/complaints/1").json
    paused = client.post("/api/complaints/1/sla/pause", headers=headers, json={"version": c["version"], "reason": "Approved pause for document access"})
    assert paused.status_code == 200 and paused.json["deadline_condition"] == "paused"
    resumed = client.post("/api/complaints/1/sla/resume", headers=headers, json={"version": paused.json["version"], "reason": "Document access has been restored"})
    assert resumed.status_code == 200 and resumed.json["paused_at"] is None


def test_episode_metrics_distinguish_reopened_cycles(client, app):
    headers = login(client)
    case = client.get("/api/complaints/1").json
    document = approved_test_evidence(app)
    for state in ["disposed", "under_review", "disposed"]:
        response = client.post("/api/complaints/1/status", headers=headers, json={"version": case["version"], "status": state, "reason": "Documented lifecycle episode test", "outcome_document_id": document, "communication": "Synthetic outcome communication recorded with its recipient"})
        assert response.status_code == 200
        case = response.json
    metrics = client.get("/api/reports/metrics?institution=1").json
    assert metrics["disposed_episodes"] == 2
    assert metrics["sla_eligible_episodes"] == 2
    assert metrics["sla_excluded_episodes"] == 0
    assert metrics["sla_compliance"] == 0  # Seeded case deadline is overdue.
