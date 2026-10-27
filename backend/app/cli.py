import os
from datetime import timedelta
import click
from sqlalchemy import select
from .models import db, now, Bureau, User, Institution, Complaint, Assignment, Grant, PermissionGrant


def seed_demo(password):
    from .api import hasher, event, enqueue
    if db.session.scalar(select(User.id).limit(1)):
        raise click.ClickException("Database already contains users. Demo seed will not overwrite existing data.")
    rb, pgrc = Bureau(code="RB", name="Regulation Bureau"), Bureau(code="PGRC", name="Public Grievance Redressal Cell")
    db.session.add_all([rb, pgrc])
    db.session.flush()
    records = [("Aarav Sharma", "lead.rb@onecase.demo", "lead", rb.id),
               ("Meera Iyer", "officer.rb@onecase.demo", "officer", rb.id),
               ("Nisha Rao", "lead.pgrc@onecase.demo", "lead", pgrc.id),
               ("Kabir Sen", "officer.pgrc@onecase.demo", "officer", pgrc.id),
               ("Riya Menon", "reviewer@onecase.demo", "reviewer", None),
               ("Dev Patel", "auditor@onecase.demo", "auditor", None),
               ("System Administrator", "admin@onecase.demo", "admin", None)]
    users = [User(name=n, email=e, role=r, bureau_id=b, password_hash=hasher.hash(password)) for n, e, r, b in records]
    db.session.add_all(users)
    schools = [Institution(name="Northstar Institute of Technology", external_id="DEMO-1-10001", verified=True, region="North", address="Synthetic campus, New Delhi"),
               Institution(name="Sahyadri College of Engineering", external_id="DEMO-1-10002", verified=True, region="West", address="Synthetic campus, Pune"),
               Institution(name="Marina Technical Institute", external_id="DEMO-1-10003", verified=True, region="South", address="Synthetic campus, Chennai"),
               Institution(name="Eastern Valley Polytechnic", external_id=None, verified=False, region="East", address="Synthetic campus, Kolkata")]
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
        case = Complaint(reference=f"OC-{now().year}-{i:05d}", institution_id=schools[school].id, category=category,
                         description=description, priority=priority, bureau_id=owner.bureau_id, owner_id=owner.id,
                         received_at=now() - timedelta(days=age), due_at=now() + timedelta(days=due),
                         next_action=next_action, status=status)
        db.session.add(case)
        db.session.flush()
        db.session.add(Assignment(complaint_id=case.id, bureau_id=case.bureau_id, owner_id=case.owner_id, reason="Synthetic demonstration assignment"))
        item = event(case, "registered", "Complaint registered", "Synthetic demonstration record", actor=owner)
        item.created_at = case.received_at
        if status == "disposed":
            item = event(case, "status_changed", "Status changed to disposed", "Synthetic inspection completed", {"status": {"before": "under_review", "after": "disposed"}}, actor=owner)
            item.created_at = now() - timedelta(days=5)
        for reader in users[4:6]:
            db.session.add(Grant(user_id=reader.id, complaint_id=case.id))
        enqueue(case)
    configure_demo_access(password)
    db.session.commit()


def configure_demo_access(password="OneCaseDemo!2026"):
    """Explicit synthetic access grants; never silently applied to non-demo accounts."""
    from .api import hasher
    for name, email, role in [("Isha Verma", "verifier@onecase.demo", "verifier"), ("Anil Desai", "committee@onecase.demo", "committee"), ("Sana Khan", "monitor@onecase.demo", "executive")]:
        if not db.session.scalar(select(User).where(User.email == email)):
            db.session.add(User(name=name, email=email, role=role, password_hash=hasher.hash(password)))
    db.session.flush()
    permission_keys = {(p.user_id,p.operation,p.bureau_id,p.complaint_id) for p in db.session.scalars(select(PermissionGrant))}
    for email in ("lead.rb@onecase.demo", "lead.pgrc@onecase.demo"):
        user = db.session.scalar(select(User).where(User.email == email))
        if not user:
            continue
        for operation in ("case.transition", "case.export", "audit.read"):
            if (user.id,operation,user.bureau_id,None) not in permission_keys:
                db.session.add(PermissionGrant(user_id=user.id, operation=operation, bureau_id=user.bureau_id,
                                               approval_reference="SYNTHETIC-DEMO-ACCESS-V2", reason="Explicit demonstration permission", expires_at=now() + timedelta(days=30)))
    verifier = db.session.scalar(select(User).where(User.email == "verifier@onecase.demo"))
    from .models import ActionEvent
    synthetic_ids = select(ActionEvent.complaint_id).where(ActionEvent.kind == "registered", ActionEvent.reason == "Synthetic demonstration record")
    granted_cases = set(db.session.scalars(select(Grant.complaint_id).where(Grant.user_id == verifier.id)))
    for case in db.session.scalars(select(Complaint).where(Complaint.id.in_(synthetic_ids))):
        if case.id not in granted_cases:
            db.session.add(Grant(user_id=verifier.id, complaint_id=case.id, expires_at=now() + timedelta(days=30), reason="Synthetic independent-verifier assignment"))
        for operation in ("documents.read", "case.transition"):
            if (verifier.id,operation,None,case.id) not in permission_keys:
                db.session.add(PermissionGrant(user_id=verifier.id, complaint_id=case.id, operation=operation, approval_reference="SYNTHETIC-VERIFIER-V2", reason="Independent demonstration verification", expires_at=now() + timedelta(days=30)))


def register(app):
    @app.cli.command("configure-demo-access")
    def demo_access():
        configure_demo_access()
        db.session.commit()
        click.echo("Explicit synthetic access grants configured; existing cases preserved.")
    @app.cli.command("seed-demo")
    @click.option("--password", envvar="DEMO_PASSWORD", default="OneCaseDemo!2026", help="Synthetic local demo password")
    def seed(password):
        """Add synthetic demo records to an already migrated, empty database."""
        if len(password) < 12:
            raise click.ClickException("Use a password with at least 12 characters")
        seed_demo(password)
        click.echo("Synthetic records seeded. Accounts and setup instructions are in README.md.")

    @app.cli.command("create-user")
    @click.option("--email", required=True)
    @click.option("--name", required=True)
    @click.option("--role", type=click.Choice(["officer", "lead", "reviewer", "auditor", "executive", "admin"]), required=True)
    @click.option("--bureau", type=int)
    @click.password_option()
    def create_user(email, name, role, bureau, password):
        """Provision an account locally; administrator accounts have no case access."""
        from .api import hasher
        if role == "admin" and db.session.scalar(select(User.id).where(User.role == "admin")):
            raise click.ClickException("The system administrator account already exists. Additional administrator accounts are not permitted.")
        if len(password) < 12 or role in ("officer", "lead") and not db.session.get(Bureau, bureau):
            raise click.ClickException("A 12-character password and valid bureau for officers/leads are required.")
        db.session.add(User(name=name, email=email.lower(), password_hash=hasher.hash(password), role=role, bureau_id=bureau))
        db.session.commit()
        click.echo("Account provisioned.")

    @app.cli.command("grant-case")
    @click.argument("email")
    @click.argument("case_id", type=int)
    def grant_case(email, case_id):
        """Explicitly grant read access; reviewer role separately permits pair decisions."""
        user = db.session.scalar(select(User).where(User.email == email.lower()))
        if not user or not db.session.get(Complaint, case_id):
            raise click.ClickException("User or case not found")
        if not db.session.scalar(select(Grant).where(Grant.user_id == user.id, Grant.complaint_id == case_id)):
            db.session.add(Grant(user_id=user.id, complaint_id=case_id))
            db.session.commit()
        click.echo("Explicit case access granted.")
