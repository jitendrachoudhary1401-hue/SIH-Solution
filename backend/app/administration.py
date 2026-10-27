"""Approved account/scope administration; no implicit access to complaint content."""
from datetime import datetime, timezone
from flask import Blueprint, abort, g
from pydantic import Field, field_validator
from sqlalchemy import select
from .models import (db, now, iso, User, Session, RoleAssignment, PermissionGrant, Grant, Appointment,
                     Proceeding, Complaint, CaseConflict, MilestonePolicy, ActionEvent)
from .auth import authenticated, require_admin, roles, ROLES, PUBLIC_ROLES, OPERATIONS
from .api import Input, parse, user_json, hasher, event
from .security import require_recent_auth, compromised_password

administration_api = Blueprint("administration", __name__)


class Approval(Input):
    approval_reference: str = Field(min_length=5, max_length=200)
    reason: str = Field(min_length=5, max_length=1000)


class AccountInput(Approval):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=12, max_length=1024)
    role: str
    bureau_id: int | None = None


class AccountChange(Approval):
    active: bool | None = None
    role: str | None = None
    bureau_id: int | None = None


class AccessInput(Approval):
    user_id: int
    operation: str
    complaint_id: int | None = None
    bureau_id: int | None = None
    institution_id: int | None = None
    region: str | None = Field(default=None, max_length=80)
    expires_at: datetime
    @field_validator("expires_at")
    @classmethod
    def aware(cls, value):
        if not value.tzinfo or value <= now():
            raise ValueError("Future timezone-aware expiry required")
        return value


class RoleInput(Approval):
    user_id: int
    role: str
    expires_at: datetime


class AppointmentInput(Approval):
    user_id: int
    proceeding_id: int
    designation: str = Field(min_length=3, max_length=150)
    capacity: str
    expires_at: datetime


class ConflictInput(Approval):
    user_id: int
    complaint_id: int


class PolicyInput(Approval):
    name: str = Field(min_length=3, max_length=150)
    version: str = Field(min_length=1, max_length=50)
    source: str = Field(min_length=5, max_length=500)
    clause: str = Field(min_length=2, max_length=200)
    route: str
    institution_type: str = Field(min_length=2, max_length=60)
    confirmed: bool = False
    administrative: bool = True
    mode: str
    minutes: int = Field(gt=0, le=5256000)
    timezone: str = "Asia/Kolkata"
    start_event: str = Field(min_length=3, max_length=100)
    pause_rule: str = Field(min_length=3, max_length=300)
    effective_from: datetime
    effective_until: datetime | None = None


def admin_access():
    require_admin()
    require_recent_auth()


def revoke_sessions(user_id):
    db.session.query(Session).filter(Session.user_id == user_id).delete()


def approved_metadata(item):
    return {"id": item.id, "user_id": item.user_id, "expires_at": iso(item.expires_at),
            "approval_reference": item.approval_reference, "revoked": bool(getattr(item, "revoked_at", None) or getattr(item, "recused_at", None))}


@administration_api.get("/admin/workspace")
@authenticated
def admin_workspace():
    require_admin()
    users = db.session.scalars(select(User).order_by(User.id)).all()
    permissions = db.session.scalars(select(PermissionGrant).order_by(PermissionGrant.id.desc()).limit(100)).all()
    appointments = db.session.scalars(select(Appointment).order_by(Appointment.id.desc()).limit(100)).all()
    assignments = db.session.scalars(select(RoleAssignment).order_by(RoleAssignment.id.desc()).limit(100)).all()
    return {"users": [{**user_json(u), "active": u.active, "mfa_enabled": u.mfa_enabled} for u in users],
            "roles": sorted(ROLES | PUBLIC_ROLES), "operations": sorted(OPERATIONS),
            "permissions": [{**approved_metadata(p), "operation": p.operation, "complaint_id": p.complaint_id, "bureau_id": p.bureau_id, "region": p.region} for p in permissions],
            "appointments": [{**approved_metadata(a), "proceeding_id": a.proceeding_id, "designation": a.designation, "capacity": a.capacity} for a in appointments],
            "role_assignments": [{**approved_metadata(a), "role": a.role} for a in assignments],
            "security_events": [{"id": e.id, "summary": e.summary, "actor": e.actor_name, "outcome": e.outcome, "created_at": iso(e.created_at), "request_id": e.request_id} for e in db.session.scalars(select(ActionEvent).where(ActionEvent.complaint_id.is_(None)).order_by(ActionEvent.id.desc()).limit(30))]}


@administration_api.post("/admin/users")
@authenticated
def create_account():
    admin_access()
    data = parse(AccountInput)
    if data.role == "admin":
        abort(422, description="Only one system administrator account is supported. Use the existing administrator account.")
    from .models import Bureau
    if data.role not in ROLES | PUBLIC_ROLES or "@" not in data.email or data.role in ("officer", "lead") and not db.session.get(Bureau, data.bureau_id):
        abort(422, description="Choose a valid role, email and required bureau.")
    if compromised_password(data.password):
        abort(422, description="This password is on the compromised-password denylist.")
    item = User(name=data.name, email=data.email.casefold(), role=data.role, bureau_id=data.bureau_id, password_hash=hasher.hash(data.password))
    db.session.add(item)
    db.session.flush()
    event(None, "account_provisioned", "Account provisioned through approved administration", data.reason,
          {"user_id": item.id, "role": data.role, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"id": item.id}, 201


@administration_api.patch("/admin/users/<int:user_id>")
@authenticated
def update_account(user_id):
    admin_access()
    data = parse(AccountChange)
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == g.user.id and (data.active is False or data.role and data.role != "admin"):
        abort(422, description="An administrator cannot remove its own current administrative access.")
    if data.role is not None:
        if data.role == "admin" and user.role != "admin":
            abort(422, description="Additional system administrator accounts are not permitted.")
        if data.role not in ROLES | PUBLIC_ROLES:
            abort(422, description="Unknown roles default to denial.")
        user.role = data.role
    if "bureau_id" in data.model_fields_set:
        user.bureau_id = data.bureau_id
    if user.role in ("officer", "lead") and not user.bureau_id:
        abort(422, description="An officer or lead requires an approved bureau membership.")
    if data.active is not None:
        user.active = data.active
    revoke_sessions(user.id)
    event(None, "account_changed", "Account membership/access changed; sessions revoked", data.reason,
          {"user_id": user.id, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"ok": True}


@administration_api.post("/admin/permissions")
@authenticated
def create_permission():
    admin_access()
    data = parse(AccessInput)
    user = db.session.get(User, data.user_id)
    if not user or not user.active or data.operation not in OPERATIONS or not any([data.complaint_id, data.bureau_id, data.institution_id, data.region]):
        abort(422, description="An active user, known operation and bounded object scope are required.")
    if data.complaint_id and not db.session.get(Complaint, data.complaint_id):
        abort(422, description="Case ID does not exist.")
    item = PermissionGrant(**data.model_dump(exclude={"approval_reference", "reason"}), approved_by=g.user.id,
                           approval_reference=data.approval_reference, reason=data.reason)
    db.session.add(item)
    revoke_sessions(user.id)
    event(None, "permission_granted", "Approved scoped permission granted; sessions revoked", data.reason,
          {"user_id": user.id, "operation": data.operation, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"ok": True}, 201


@administration_api.post("/admin/roles")
@authenticated
def assign_role():
    admin_access()
    data = parse(RoleInput)
    if data.role == "admin":
        abort(422, description="System administrator access cannot be assigned as an additional role.")
    if data.role not in ROLES or not db.session.get(User, data.user_id) or not data.expires_at.tzinfo or data.expires_at <= now():
        abort(422, description="A known role, user and future expiry are required.")
    db.session.add(RoleAssignment(**data.model_dump(), approved_by=g.user.id))
    revoke_sessions(data.user_id)
    event(None, "role_granted", "Time-limited role approved; sessions revoked", data.reason,
          {"user_id": data.user_id, "role": data.role, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"ok": True}, 201


@administration_api.post("/admin/appointments")
@authenticated
def appoint_participant():
    admin_access()
    data = parse(AppointmentInput)
    user = db.session.get(User, data.user_id)
    capacities = {"coordinator": ["coordinate", "contribute", "documents", "packet"], "member": ["contribute", "documents"], "finalizer": ["finalize", "contribute", "documents"]}
    if not user or "committee" not in roles(user) or not db.session.get(Proceeding, data.proceeding_id) or data.capacity not in capacities or not data.expires_at.tzinfo or data.expires_at <= now():
        abort(422, description="A committee-role account, valid proceeding, capacity and future expiry are required.")
    db.session.add(Appointment(user_id=user.id, proceeding_id=data.proceeding_id, designation=data.designation,
                               capacity=data.capacity, permissions=capacities[data.capacity], expires_at=data.expires_at,
                               approval_reference=data.approval_reference, approved_by=g.user.id))
    revoke_sessions(user.id)
    event(None, "appointment_recorded", "Case-bound appointment recorded from competent approval", data.reason,
          {"user_id": user.id, "proceeding_id": data.proceeding_id, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"ok": True}, 201


@administration_api.post("/admin/access/<kind>/<int:item_id>/revoke")
@authenticated
def revoke_access(kind, item_id):
    admin_access()
    data = parse(Approval)
    model = {"permission": PermissionGrant, "role": RoleAssignment, "appointment": Appointment, "case": Grant}.get(kind)
    item = db.session.get(model, item_id) if model else None
    if not item:
        abort(404)
    if kind == "appointment":
        item.recused_at = now()
    else:
        item.revoked_at = now()
    revoke_sessions(item.user_id)
    event(None, "access_revoked", "Scoped access revoked and sessions invalidated", data.reason,
          {"kind": kind, "grant_id": item.id, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"ok": True}


@administration_api.post("/admin/conflicts")
@authenticated
def record_conflict():
    admin_access()
    data = parse(ConflictInput)
    if not db.session.get(User, data.user_id) or not db.session.get(Complaint, data.complaint_id):
        abort(422, description="User and case must exist.")
    db.session.add(CaseConflict(user_id=data.user_id, complaint_id=data.complaint_id, reason=data.reason,
                                decision_reference=data.approval_reference, recorded_by=g.user.id))
    for appointment in db.session.scalars(select(Appointment).join(Proceeding).where(Appointment.user_id == data.user_id, Proceeding.complaint_id == data.complaint_id)):
        appointment.recused_at = now()
    revoke_sessions(data.user_id)
    event(None, "conflict_recorded", "Competent conflict/recusal decision recorded; access revoked", data.reason,
          {"user_id": data.user_id, "case_id": data.complaint_id, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"ok": True}, 201


@administration_api.post("/admin/policies")
@authenticated
def create_policy():
    admin_access()
    data = parse(PolicyInput)
    from .workflow import ROUTES
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    if data.route not in ROUTES | {"any"} or data.mode not in ("elapsed", "business") or not data.effective_from.tzinfo:
        abort(422, description="Policy route, counting mode and effective timestamp are required.")
    try:
        ZoneInfo(data.timezone)
    except ZoneInfoNotFoundError:
        abort(422, description="Choose a supported IANA timezone.")
    item = MilestonePolicy(**data.model_dump(exclude={"timezone", "reason"}), approved_by=g.user.id,
                           calendar={"timezone": data.timezone, "weekdays": [0, 1, 2, 3, 4], "intervals": [[9, 17]], "holidays": []})
    db.session.add(item)
    event(None, "policy_created", "New versioned milestone policy recorded without rewriting prior deadlines", data.reason,
          {"name": data.name, "version": data.version, "confirmed": data.confirmed, "approval_reference": data.approval_reference})
    db.session.commit()
    return {"ok": True}, 201


@administration_api.get("/policies")
@authenticated
def list_policies():
    policies = db.session.scalars(select(MilestonePolicy).order_by(MilestonePolicy.id.desc())).all()
    return {"items": [{"id": p.id, "name": p.name, "version": p.version, "route": p.route, "confirmed": p.confirmed,
                       "administrative": p.administrative, "source": p.source, "clause": p.clause} for p in policies]}
