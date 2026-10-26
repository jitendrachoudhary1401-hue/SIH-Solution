from datetime import timedelta
from sqlalchemy import select, event as sql_event
from conftest import login, approved_test_evidence
from app import create_app
from app.models import (db, now, User, Grant, Proceeding, Appointment, CaseConflict,
                         Attachment, ProceedingRecord, ComplianceItem)


def proceeding(case_id=1):
    item = Proceeding(complaint_id=case_id, kind="student_institution", external_authority="Synthetic approved committee",
                       authority_reference="SYNTHETIC-APPOINTMENT", institution_type="degree", jurisdiction="Synthetic scope",
                       framework="Policy confirmation required", framework_version="test-v1", context={})
    db.session.add(item)
    db.session.flush()
    return item


def test_expired_case_grant_removes_details_counts_and_documents(app, client):
    login(client, "reviewer@onecase.demo")
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "reviewer@onecase.demo"))
        grant = db.session.scalar(select(Grant).where(Grant.user_id == user.id, Grant.complaint_id == 1))
        grant.expires_at = now() - timedelta(seconds=1)
        db.session.commit()
    assert client.get("/api/complaints/1").status_code == 404
    assert 1 not in [c["id"] for c in client.get("/api/complaints").json["items"]]


def test_appointment_expiry_and_conflict_deny_combined_access(app, client):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "committee@onecase.demo"))
        admin = db.session.scalar(select(User).where(User.email == "admin@onecase.demo"))
        p = proceeding()
        appointment = Appointment(user_id=user.id, proceeding_id=p.id, designation="Synthetic member", capacity="member",
                                  permissions=["contribute", "documents"], expires_at=now() + timedelta(hours=1),
                                  approval_reference="SYNTHETIC-APPROVAL", approved_by=admin.id)
        db.session.add(appointment)
        db.session.commit()
        appointment_id, user_id, admin_id = appointment.id, user.id, admin.id
    login(client, "committee@onecase.demo")
    detail = client.get("/api/complaints/1")
    assert detail.status_code == 200 and detail.json["has_content"] is False
    with app.app_context():
        db.session.get(Appointment, appointment_id).expires_at = now() - timedelta(seconds=1)
        db.session.commit()
    assert client.get("/api/complaints/1").status_code == 404
    with app.app_context():
        db.session.get(Appointment, appointment_id).expires_at = now() + timedelta(hours=1)
        db.session.add(Grant(user_id=user_id, complaint_id=1))
        db.session.add(CaseConflict(user_id=user_id, complaint_id=1, reason="Competent recusal decision", decision_reference="SYNTHETIC-CONFLICT", recorded_by=admin_id))
        db.session.commit()
    assert client.get("/api/complaints/1").status_code == 404


def test_compliance_submission_does_not_verify_itself(app, client):
    attachment_id = approved_test_evidence(app)
    with app.app_context():
        verifier = db.session.scalar(select(User).where(User.email == "verifier@onecase.demo"))
        p = proceeding()
        record = ProceedingRecord(proceeding_id=p.id, kind="decision", title="Synthetic approved direction", details={},
                                  attachment_id=attachment_id, finalized=True, issuer="Synthetic authority", verification_reference="SYNTHETIC-VERIFIED", created_by=1)
        db.session.add(record)
        db.session.flush()
        item = ComplianceItem(proceeding_id=p.id, direction_record_id=record.id, title="Return the recorded deposit",
                              responsible_party="Synthetic institution", respondent_user_id=1, verifier_id=verifier.id)
        db.session.add(item)
        db.session.commit()
        item_id = item.id
    lead_headers = login(client)
    response = client.post(f"/api/compliance/{item_id}/submissions", headers=lead_headers,
                           json={"version": 1, "attachment_id": attachment_id, "submitting_party": "Synthetic respondent", "reason": "Payment evidence supplied for independent review"})
    assert response.status_code == 201
    with app.app_context():
        from app.models import ComplianceSubmission
        item = db.session.get(ComplianceItem, item_id)
        assert item.state == "evidence_submitted"
        submission_id = db.session.scalar(select(ComplianceSubmission.id).where(ComplianceSubmission.item_id == item_id))
        version = item.version
    payload = {"version": version, "submission_id": submission_id, "outcome": "verified", "observations": "Checked the synthetic payment reference against the approved direction.", "reason": "Independent evidence verification"}
    assert client.post(f"/api/compliance/{item_id}/verify", headers=lead_headers, json=payload).status_code == 403
    verifier_headers = login(client, "verifier@onecase.demo")
    assert client.post(f"/api/compliance/{item_id}/verify", headers=verifier_headers, json=payload).status_code == 200


def test_mfa_recovery_is_one_time_and_secret_is_encrypted(app, client):
    headers = login(client)
    setup = client.post("/api/auth/mfa/setup", headers=headers, json={})
    assert setup.status_code == 200
    from app.security import totp
    import time
    confirm = client.post("/api/auth/mfa/confirm", headers=headers, json={"code": totp(setup.json["secret"], int(time.time()) // 30)})
    assert confirm.status_code == 200
    recovery = confirm.json["recovery_codes"][0]
    with app.app_context():
        user = db.session.get(User, 1)
        assert user.mfa_secret != setup.json["secret"] and recovery not in user.recovery_codes
    client.post("/api/auth/logout", headers=headers, json={})
    credentials = {"email": "lead.rb@onecase.demo", "password": "TestPassword!2026", "verification_code": recovery}
    assert client.post("/api/auth/login", json=credentials).status_code == 200
    assert client.post("/api/auth/login", json=credentials).status_code == 403


def test_missing_scanner_keeps_evidence_quarantined(app, client):
    item_id = approved_test_evidence(app)
    with app.app_context():
        app.config["CLAMAV_HOST"] = ""
        db.session.get(Attachment, item_id).scan_state = "pending"
        db.session.commit()
        from app.documents import scan_pending
        scan_pending()
        assert db.session.get(Attachment, item_id).scan_state == "pending"
    login(client)
    assert client.get(f"/api/attachments/{item_id}/download").status_code == 423


def test_rate_limit_rejects_before_database_work(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "2 per minute")
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "limits.db").as_posix(),
                      "STORAGE_PATH": str(tmp_path / "documents"), "STORAGE_BACKEND": "local", "RATELIMIT_ENABLED": True})
    with app.app_context():
        db.create_all()
    client = app.test_client()
    payload = {"email": "unprovisioned@example.test", "password": "invalid"}
    assert client.post("/api/auth/login", json=payload).status_code == 401
    assert client.post("/api/auth/login", json=payload).status_code == 401
    queries = []
    with app.app_context():
        engine = db.engine
        def record_query(*args):
            queries.append(True)
        sql_event.listen(engine, "before_cursor_execute", record_query)
        response = client.post("/api/auth/login", json=payload)
        sql_event.remove(engine, "before_cursor_execute", record_query)
    assert response.status_code == 429 and not queries
