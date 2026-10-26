import pytest
from app.models import db, AccountRequest, User, Bureau


def test_student_registration_workflow(client):
    # 1. Submit student registration
    payload = {
        "name": "Arjun Sharma",
        "email": "arjun.student@example.ac.in",
        "password": "StudentSecurePass!2026",
        "college_name": "Northstar Institute of Technology",
        "roll_number": "NIT-2023-CS-042",
        "department": "Computer Science & Engineering",
        "academic_year": "3rd Year (2023-2027)"
    }
    res = client.post("/api/account-requests/student", json=payload)
    assert res.status_code == 201
    data = res.json
    assert data["ok"] is True
    assert data["status"] == "pending"
    req_id = data["id"]

    # 2. Duplicate registration attempt should be rejected with 409
    res_dup = client.post("/api/account-requests/student", json=payload)
    assert res_dup.status_code == 409

    # 3. Pending applicant attempts to login -> 403 Forbidden explaining pending verification
    res_login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res_login.status_code == 403
    assert "pending administrative verification" in res_login.json["error"]["message"]

    # 4. Non-admin user cannot list or review requests
    officer_login = client.post("/api/auth/login", json={"email": "officer.rb@onecase.demo", "password": "TestPassword!2026"})
    officer_csrf = officer_login.json["csrf"]
    res_forbidden = client.get("/api/account-requests", headers={"X-CSRF-Token": officer_csrf})
    assert res_forbidden.status_code == 403

    # 5. Admin user can view pending requests
    admin_login = client.post("/api/auth/login", json={"email": "admin@onecase.demo", "password": "TestPassword!2026"})
    admin_csrf = admin_login.json["csrf"]
    res_admin = client.get("/api/account-requests?status=pending", headers={"X-CSRF-Token": admin_csrf})
    assert res_admin.status_code == 200
    requests = res_admin.json["items"]
    assert any(r["id"] == req_id for r in requests)

    # 6. Admin approves student request
    res_approve = client.post(
        f"/api/account-requests/{req_id}/review",
        json={"decision": "approved", "reason": "Student credentials and enrollment verified with NIT roster"},
        headers={"X-CSRF-Token": admin_csrf}
    )
    assert res_approve.status_code == 200
    assert res_approve.json["status"] == "approved"

    # 7. Approved student can now log in
    res_student_login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res_student_login.status_code == 200
    assert res_student_login.json["user"]["role"] == "student"
    assert res_student_login.json["user"]["email"] == payload["email"]


def test_college_rep_registration_workflow(client):
    payload = {
        "name": "Dr. Ramesh Kulkarni",
        "email": "asop.ramesh@sahyadri.edu",
        "password": "CollegeRepPass!2026",
        "college_name": "Sahyadri College of Engineering",
        "employee_id": "SCE-FAC-1092",
        "designation": "Associate Professor & AICTE ASOP Nodal Officer",
        "reason": "Appointed institutional liaison for grievance redressal and compliance tracking."
    }
    res = client.post("/api/account-requests/college-rep", json=payload)
    assert res.status_code == 201
    req_id = res.json["id"]

    # Admin reviews and rejects with reason
    admin_login = client.post("/api/auth/login", json={"email": "admin@onecase.demo", "password": "TestPassword!2026"})
    admin_csrf = admin_login.json["csrf"]

    res_reject = client.post(
        f"/api/account-requests/{req_id}/review",
        json={"decision": "rejected", "reason": "Official authorization letter from college principal is missing."},
        headers={"X-CSRF-Token": admin_csrf}
    )
    assert res_reject.status_code == 200
    assert res_reject.json["status"] == "rejected"

    # Rejected applicant receives 403 on login with reason
    res_login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res_login.status_code == 403
    assert "rejected" in res_login.json["error"]["message"]
    assert "authorization letter" in res_login.json["error"]["message"]


def test_officer_account_request_workflow(client):
    payload = {
        "name": "Sunita Verma",
        "email": "sunita.verma@aicte.gov.in",
        "password": "OfficerSecret!2026",
        "employee_id": "AICTE-RB-8841",
        "designation": "Assistant Director",
        "bureau_code": "RB",
        "reason": "Deputed to Regulation Bureau case coordination and AI triage oversight."
    }
    res = client.post("/api/account-requests/officer", json=payload)
    assert res.status_code == 201
    req_id = res.json["id"]

    admin_login = client.post("/api/auth/login", json={"email": "admin@onecase.demo", "password": "TestPassword!2026"})
    admin_csrf = admin_login.json["csrf"]

    res_approve = client.post(
        f"/api/account-requests/{req_id}/review",
        json={"decision": "approved", "reason": "Officer deputation verified against AICTE Bureau roster"},
        headers={"X-CSRF-Token": admin_csrf}
    )
    assert res_approve.status_code == 200

    # Officer can now log in
    res_login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res_login.status_code == 200
    assert res_login.json["user"]["role"] == "officer"
    assert res_login.json["user"]["bureau"] == "RB"
