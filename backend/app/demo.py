"""Public demo identities are opt-in and confined to a synthetic bureau."""
import secrets
from datetime import timedelta, timezone
from flask import Blueprint, abort, current_app
from pydantic import Field
from sqlalchemy import select
from .models import db, User, Bureau, Institution, RoleAssignment, now
from .api import Input, parse, hasher, sign_in_response

demo_api = Blueprint("demo", __name__)
DEMO_ROLES = ("student", "parent", "faculty", "staff", "other", "faculty_reviewer", "officer", "lead", "reviewer", "committee", "verifier", "executive", "auditor")
INSTITUTION_ID = "ONECASE-PUBLIC-DEMO"


class DemoLogin(Input):
    role: str = Field(max_length=30)


def seed_public_demo_accounts():
    bureau = db.session.scalar(select(Bureau).where(Bureau.code == "PUBLIC-DEMO"))
    if not bureau:
        bureau = Bureau(code="PUBLIC-DEMO", name="Public demonstration bureau")
        db.session.add(bureau)
        db.session.flush()
    institution = db.session.scalar(select(Institution).where(Institution.external_id == INSTITUTION_ID))
    if not institution:
        db.session.add(Institution(name="OneCase Demonstration Institute", external_id=INSTITUTION_ID,
                                  verified=False, region="Demonstration", address="Synthetic institution for public demonstrations"))
    created = 0
    for role in DEMO_ROLES:
        email = f"demo.{role}@onecase.demo"
        user = db.session.scalar(select(User).where(User.email == email))
        if user:
            if not user.is_demo or user.role != role:
                raise ValueError("A reserved demo email is already used by another account.")
            continue
        db.session.add(User(name=f"Demo {role.replace('_', ' ').title()}", email=email,
                            password_hash=hasher.hash(secrets.token_urlsafe(48)), role=role, requested_role=role,
                            organization="OneCase public demonstration", is_demo=True,
                            bureau_id=bureau.id if role in {"officer", "lead"} else None))
        created += 1
    db.session.commit()
    faculty = db.session.scalar(select(User).where(User.email == 'demo.faculty@onecase.demo', User.is_demo.is_(True)))
    if faculty:
        approved = db.session.scalar(select(RoleAssignment).where(RoleAssignment.user_id == faculty.id, RoleAssignment.role == 'faculty_reviewer', RoleAssignment.revoked_at.is_(None)))
        if not approved:
            db.session.add(RoleAssignment(user_id=faculty.id, role='faculty_reviewer', expires_at=now()+timedelta(days=90),
                           approval_reference='SYNTHETIC-DEMO-FACULTY', reason='Approved faculty reviewer for the isolated demonstration college.'))
        elif approved.expires_at and approved.expires_at.replace(tzinfo=timezone.utc) <= now():
            approved.expires_at = now()+timedelta(days=90)
        for role in ('student', 'parent'):
            user = db.session.scalar(select(User).where(User.email == f'demo.{role}@onecase.demo', User.is_demo.is_(True)))
            if user:
                user.faculty_name, user.admission_year, user.passout_year = faculty.name, 2026, 2030
        db.session.commit()
    return created


def available_accounts():
    expected = {f"demo.{role}@onecase.demo": role for role in DEMO_ROLES}
    return [user for user in db.session.scalars(select(User).where(User.is_demo.is_(True), User.active.is_(True), User.email.in_(expected)))
            if user.role == expected[user.email]]


@demo_api.get("/auth/demo-accounts")
def accounts():
    if not current_app.config["DEMO_ACCOUNTS_ENABLED"]:
        return {"enabled": False, "accounts": []}
    return {"enabled": True, "accounts": [{"role": user.role, "name": user.name} for user in available_accounts()]}


@demo_api.post("/auth/demo-login")
def demo_login():
    if not current_app.config["DEMO_ACCOUNTS_ENABLED"]:
        abort(404)
    data = parse(DemoLogin)
    if data.role not in DEMO_ROLES:
        abort(422, description="Choose an available demo account.")
    user = next((user for user in available_accounts() if user.role == data.role), None)
    if not user:
        abort(404, description="This demo account has not been provisioned.")
    return sign_in_response(user)
