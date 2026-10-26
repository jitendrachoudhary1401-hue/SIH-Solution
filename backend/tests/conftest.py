import sys
from datetime import timedelta
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.models import db, now, Bureau, User, Institution, Complaint, Assignment, Grant
from app.api import hasher, event, enqueue


def setup_test_data(password="TestPassword!2026"):
    rb = Bureau(code="RB", name="Regulation Bureau")
    pgrc = Bureau(code="PGRC", name="Public Grievance Redressal Cell")
    db.session.add_all([rb, pgrc])
    db.session.flush()

    records = [
        ("Aarav Sharma", "lead.rb@onecase.demo", "lead", rb.id),
        ("Meera Iyer", "officer.rb@onecase.demo", "officer", rb.id),
        ("Nisha Rao", "lead.pgrc@onecase.demo", "lead", pgrc.id),
        ("Kabir Sen", "officer.pgrc@onecase.demo", "officer", pgrc.id),
        ("Riya Menon", "reviewer@onecase.demo", "reviewer", None),
        ("Dev Patel", "auditor@onecase.demo", "auditor", None),
        ("System Administrator", "admin@onecase.demo", "admin", None),
    ]
    users = [User(name=n, email=e, role=r, bureau_id=b, password_hash=hasher.hash(password)) for n, e, r, b in records]
    db.session.add_all(users)

    schools = [
        Institution(name="Northstar Institute of Technology", external_id="DEMO-1-10001", verified=True, region="North", address="Test campus, New Delhi"),
        Institution(name="Sahyadri College of Engineering", external_id="DEMO-1-10002", verified=True, region="West", address="Test campus, Pune"),
        Institution(name="Marina Technical Institute", external_id="DEMO-1-10003", verified=True, region="South", address="Test campus, Chennai"),
        Institution(name="Eastern Valley Polytechnic", external_id=None, verified=False, region="East", address="Test campus, Kolkata"),
    ]
    db.session.add_all(schools)
    db.session.flush()

    examples = [
        (0, 0, "Fee refund", "The institution has not refunded the admission fee after the student withdrew within the permitted withdrawal period. Repeated written requests for return of the deposit have received no response.", "high", 18, -3, "under_review", "Obtain the fee refund ledger"),
        (0, 2, "Fee refund", "A student cancelled admission on time but the college is withholding the paid tuition and security deposit. The family requests reimbursement and a written explanation for the delayed refund.", "high", 16, 2, "received", "Request withdrawal acknowledgement"),
        (0, 1, "Infrastructure", "The electronics laboratory lacks functioning oscilloscopes and safety equipment. Several practical classes were cancelled because laboratory workstations were not operational.", "normal", 9, 6, "awaiting_information", "Await laboratory inspection photographs"),
        (1, 0, "Faculty", "Students report that the mechanical engineering department has had no permanent faculty for two core subjects this semester. Verify the current faculty roster and timetable.", "urgent", 28, -5, "under_review", "Verify approved faculty roster"),
        (2, 1, "Admissions", "The admission office has not issued a formal acknowledgement for documents submitted during admission. Original certificates are still held after a written request for their return.", "high", 12, 1, "received", "Request the admissions document register"),
        (1, 2, "Examination", "A discrepancy in the published internal assessment marks remains unresolved. The student seeks a documented review against submitted laboratory records and attendance.", "normal", 6, 10, "under_review", "Collect the assessment record"),
        (2, 0, "Infrastructure", "An inspection confirmed that the accessible entrance ramp had been repaired and an independent access route is available. The complainant has received the inspection response.", "low", 38, -8, "disposed", "Retain the inspection response"),
        (3, 3, "Other", "A written request for clarification about the institution's affiliation details has been received. The external institution identifier has not yet been verified.", "normal", 3, 12, "received", "Verify institution identity"),
    ]
    for i, (school, officer, category, description, priority, age, due, status, next_action) in enumerate(examples, 1):
        owner = users[officer]
        case = Complaint(
            reference=f"OC-{now().year}-{i:05d}", institution_id=schools[school].id, category=category,
            description=description, priority=priority, bureau_id=owner.bureau_id, owner_id=owner.id,
            received_at=now() - timedelta(days=age), due_at=now() + timedelta(days=due),
            next_action=next_action, status=status
        )
        db.session.add(case)
        db.session.flush()
        db.session.add(Assignment(complaint_id=case.id, bureau_id=case.bureau_id, owner_id=case.owner_id, reason="Test assignment"))
        item = event(case, "registered", "Complaint registered", "Test record", actor=owner)
        item.created_at = case.received_at
        if status == "disposed":
            item = event(case, "status_changed", "Status changed to disposed", "Test inspection completed", {"status": {"before": "under_review", "after": "disposed"}}, actor=owner)
            item.created_at = now() - timedelta(days=5)
        for reader in users[4:6]:
            db.session.add(Grant(user_id=reader.id, complaint_id=case.id))
        enqueue(case)
    db.session.commit()


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.db").as_posix(), "STORAGE_PATH": str(tmp_path / "documents")})
    with app.app_context():
        db.create_all()
        setup_test_data("TestPassword!2026")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="lead.rb@onecase.demo"):
    response = client.post("/api/auth/login", json={"email": email, "password": "TestPassword!2026"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json["csrf"]}
