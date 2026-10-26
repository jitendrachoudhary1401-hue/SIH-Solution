import pytest
from app.models import db, AccountRequest, User, Bureau
from conftest import login


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
    officer_headers = login(client, "officer.rb@onecase.demo")
    res_forbidden = client.get("/api/account-requests", headers=officer_headers)
    assert res_forbidden.status_code == 403

    # 5. Admin user can view pending requests
    admin_headers = login(client, "admin@onecase.demo")
    res_admin = client.get("/api/account-requests?status=pending", headers=admin_headers)
    assert res_admin.status_code == 200
    requests = res_admin.json["items"]
    assert any(r["id"] == req_id for r in requests)

    # 6. Admin approves student request
    res_approve = client.post(
        f"/api/account-requests/{req_id}/review",
        json={"decision": "approved", "reason": "Student credentials and enrollment verified with NIT roster"},
        headers=admin_headers
    )
    assert res_approve.status_code == 200
    assert res_approve.json["status"] == "approved"

    # 7. Approved student can now log in via OTP
    res_student_login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res_student_login.status_code == 200
    assert res_student_login.json.get("otp_required") is True
    student_headers = login(client, payload["email"], payload["password"])
    me_res = client.get("/api/auth/me", headers=student_headers)
    assert me_res.status_code == 200
    assert me_res.json["user"]["role"] == "student"
    assert me_res.json["user"]["email"] == payload["email"]


def test_college_rep_registration_workflow(client):
    payload = {
        "name": "Dr. Ramesh Kulkarni",
        "email": "asop.ramesh@sahyadri.edu",
        "password": "CollegeSecretPass!2026",
        "college_name": "Sahyadri College of Engineering",
        "employee_id": "SCE-FAC-2018",
        "designation": "Associate Professor & Grievance Officer",
        "reason": "Designated institutional nodal officer for AICTE student grievance communication."
    }
    res = client.post("/api/account-requests/college-rep", json=payload)
    assert res.status_code == 201
    req_id = res.json["id"]

    # Admin reviews and rejects with reason
    admin_headers = login(client, "admin@onecase.demo")

    res_reject = client.post(
        f"/api/account-requests/{req_id}/review",
        json={"decision": "rejected", "reason": "Official authorization letter from college principal is missing."},
        headers=admin_headers
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

    admin_headers = login(client, "admin@onecase.demo")

    res_approve = client.post(
        f"/api/account-requests/{req_id}/review",
        json={"decision": "approved", "reason": "Officer deputation verified against AICTE Bureau roster"},
        headers=admin_headers
    )
    assert res_approve.status_code == 200

    # Officer can now log in via OTP
    res_login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res_login.status_code == 200
    assert res_login.json.get("otp_required") is True
    officer_headers = login(client, payload["email"], payload["password"])
    me_res = client.get("/api/auth/me", headers=officer_headers)
    assert me_res.status_code == 200
    assert me_res.json["user"]["role"] == "officer"
    assert me_res.json["user"]["bureau"] == "RB"
