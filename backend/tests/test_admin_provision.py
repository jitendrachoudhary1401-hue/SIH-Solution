import os
import pytest
from sqlalchemy import select
from app.models import db, User, ActionEvent, AccountRequest
from app.api import hasher


def test_initial_admin_provisioning_succeeds_when_no_admin(app):
    """Test 1: Initial Admin provisioning succeeds when no Admin exists."""
    runner = app.test_cli_runner()

    with app.app_context():
        # Clean out any existing admin
        admins = db.session.scalars(select(User).where(User.role == "admin")).all()
        for a in admins:
            db.session.delete(a)
        db.session.commit()

        # Verify no admin exists
        assert db.session.scalar(select(User).where(User.role == "admin")) is None

    # Run provisioning CLI command
    result = runner.invoke(args=[
        "provision-initial-admin",
        "--email", "secops.admin@onecase.gov.in",
        "--name", "Security Administrator",
        "--password", "StrongAdminPass#2026!"
    ])

    assert result.exit_code == 0
    assert "Successfully provisioned initial administrator" in result.output
    # Must NOT print password or secrets
    assert "StrongAdminPass#2026!" not in result.output

    with app.app_context():
        admin = db.session.scalar(select(User).where(User.email == "secops.admin@onecase.gov.in"))
        assert admin is not None
        assert admin.role == "admin"
        assert admin.active is True
        assert hasher.verify(admin.password_hash, "StrongAdminPass#2026!")

        # Audit event must be recorded
        evt = db.session.scalar(
            select(ActionEvent).where(
                ActionEvent.kind == "admin_provisioned",
                ActionEvent.actor_id == admin.id
            )
        )
        assert evt is not None
        assert "Initial administrator account provisioned" in evt.summary


def test_rerunning_provisioning_refuses_duplicate_admin(app):
    """Test 2: Re-running provisioning does not silently create or promote another Admin."""
    runner = app.test_cli_runner()

    with app.app_context():
        # Ensure at least one admin exists
        admin = db.session.scalar(select(User).where(User.role == "admin"))
        assert admin is not None

    # Try provisioning another admin
    result = runner.invoke(args=[
        "provision-initial-admin",
        "--email", "another.admin@onecase.gov.in",
        "--name", "Imposter Admin",
        "--password", "AnotherStrongPass#2026!"
    ])

    assert result.exit_code != 0
    assert "already exists" in result.output.lower()

    with app.app_context():
        imposter = db.session.scalar(select(User).where(User.email == "another.admin@onecase.gov.in"))
        assert imposter is None


def test_public_registration_cannot_create_admin(client, app):
    """Test 3: Public registration cannot create an Admin account."""
    # Attempt 1: Student registration with injected role field is rejected by schema validator
    res = client.post("/api/account-requests/student", json={
        "name": "Attacker",
        "email": "attacker.student@onecase.demo",
        "password": "Password12345!",
        "college_name": "Northstar Institute of Technology",
        "roll_number": "ATT-001",
        "department": "CSE",
        "academic_year": "2026",
        "role": "admin"  # Injected field
    })
    # Pydantic strictly rejects unauthorized fields
    assert res.status_code == 422

    # Attempt 2: Normal student registration never creates admin role
    res_valid = client.post("/api/account-requests/student", json={
        "name": "Legit Student",
        "email": "student.legit@onecase.demo",
        "password": "Password12345!",
        "college_name": "Northstar Institute of Technology",
        "roll_number": "LEGIT-001",
        "department": "CSE",
        "academic_year": "2026"
    })
    assert res_valid.status_code == 201

    with app.app_context():
        req = db.session.scalar(select(AccountRequest).where(AccountRequest.email == "student.legit@onecase.demo"))
        assert req is not None
        assert req.request_type == "student"  # Backend sets request_type strictly
        assert req.status == "pending"

        # Ensure no user record was created in User table
        user = db.session.scalar(select(User).where(User.email == "student.legit@onecase.demo"))
        assert user is None

    # Attempt 3: Direct call to admin provision API without admin session
    res2 = client.post("/api/users/provision", json={
        "name": "Attacker",
        "email": "attacker.admin@onecase.demo",
        "role": "admin",
        "password": "Password12345!"
    })
    assert res2.status_code == 401


def test_matching_gmail_sender_does_not_grant_admin(client, app):
    """Test 4: Matching the Gmail sender address does NOT automatically grant Admin privileges."""
    sender_email = "myonecase.sender@gmail.com"
    os.environ["SMTP_EMAIL"] = sender_email

    # Submit request using the exact sender email
    res = client.post("/api/account-requests/officer", json={
        "name": "Sender User",
        "email": sender_email,
        "password": "SecureOfficerPass#123",
        "designation": "Assistant Director",
        "bureau_code": "RB",
        "reason": "Official grievance work"
    })
    assert res.status_code == 201

    with app.app_context():
        req = db.session.scalar(select(AccountRequest).where(AccountRequest.email == sender_email))
        assert req is not None
        assert req.request_type == "officer"
        assert req.status == "pending"

        # Ensure no user record was auto-created or granted admin
        user = db.session.scalar(select(User).where(User.email == sender_email))
        assert user is None


def test_non_admin_cannot_access_admin_apis(client, app):
    """Test 5: Non-Admin users cannot access Admin APIs."""
    # Login as normal officer Meera Iyer
    login_res = client.post("/api/auth/login", json={
        "email": "officer.rb@onecase.demo",
        "password": "TestPassword!2026"
    })
    assert login_res.status_code == 200
    ch_id = login_res.json["challenge_id"]

    from app.email_service import get_last_sent_otp
    otp = get_last_sent_otp("officer.rb@onecase.demo")
    verify_res = client.post("/api/auth/otp/verify", json={"challenge_id": ch_id, "otp": otp})
    assert verify_res.status_code == 200

    # Officer tries to access Admin account requests
    res1 = client.get("/api/account-requests")
    assert res1.status_code == 403

    # Officer tries to provision a user
    res2 = client.post("/api/users/provision", json={
        "name": "Fake Lead",
        "email": "fake.lead@onecase.demo",
        "role": "lead",
        "bureau_id": 1,
        "password": "Password12345!"
    })
    assert res2.status_code == 403


def test_pending_user_cannot_access_protected_dashboards(client, app):
    """Test 6: A pending user cannot log in or access protected dashboard resources."""
    # Register a new student
    email = "applicant.rahul@example.com"
    pwd = "StudentPassword#2026"
    res = client.post("/api/account-requests/student", json={
        "name": "Rahul Verma",
        "email": email,
        "password": pwd,
        "college_name": "Sahyadri College of Engineering",
        "roll_number": "SCH-2026-99",
        "department": "Mechanical",
        "academic_year": "3rd Year"
    })
    assert res.status_code == 201

    # Rahul attempts login while pending
    login_res = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 403
    assert "pending administrative verification" in login_res.json["error"]["message"].lower()

    # Attempt to access complaints list directly without session
    case_res = client.get("/api/complaints")
    assert case_res.status_code == 401
