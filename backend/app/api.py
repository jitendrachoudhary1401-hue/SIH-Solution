import csv
import hashlib
import io
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from flask import Blueprint, abort, current_app, g, jsonify, make_response, request, send_file
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import and_, func, or_, select
from werkzeug.utils import secure_filename
from .auth import (authenticated, case_or_404, check_version, digest, scope, roles, capabilities,
                   allowed, has_content, document_allowed, proceeding_allowed, require_admin)
from .models import (db, now, iso, User, Bureau, Institution, Complaint, Session, LoginAttempt,
                     Assignment, Transfer, ActionEvent, Notification, Attachment, Job,
                     Pair, Review, Idempotency, MatchingRun, SLAPause)

api = Blueprint("api", __name__)
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("not-a-real-account-secret")
CATEGORIES = ["Fee refund", "Admissions", "Infrastructure", "Faculty", "Examination", "Other"]
TRANSITIONS = {"received": ["under_review", "disposed"], "under_review": ["awaiting_information", "disposed"],
               "awaiting_information": ["under_review", "disposed"], "disposed": ["under_review"]}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(Input):
    email: str = Field(min_length=3, max_length=180)
    password: str = Field(min_length=1, max_length=1024)
    verification_code: str = Field(default="", max_length=100)


class SignupInput(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=12, max_length=1024)
    confirm_password: str = Field(min_length=12, max_length=1024)
    account_type: str
    organization: str = Field(default="", max_length=200)


class Registration(Input):
    institution_id: int = Field(gt=0)
    owner_id: int = Field(gt=0)
    category: str
    description: str = Field(min_length=20, max_length=20000)
    priority: str = "normal"
    received_at: datetime
    due_at: datetime | None = None
    deadline_reason: str = Field(default="", max_length=1000)
    deadline_rule: str = "none"
    next_action: str = Field(min_length=3, max_length=500)
    issue_summary: str = Field(default="", max_length=300)
    complainant_type: str = "student"
    affected_person: str = Field(default="", max_length=150)
    submitter_name: str = Field(default="", max_length=150)
    representation_basis: str = Field(default="", max_length=1000)
    source_channel: str = Field(default="Officer recording", max_length=60)
    source_reference: str = Field(default="", max_length=150)
    prior_proceedings: str = Field(default="", max_length=5000)
    sensitivity: str = "standard"

    @field_validator("received_at", "due_at")
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("A timezone is required")
        return value


class Change(Input):
    version: int = Field(gt=0)
    reason: str = Field(min_length=5, max_length=2000)


class StatusChange(Change):
    status: str
    outcome_document_id: int | None = None
    communication: str = Field(default="", max_length=2000)
    external_continues: bool = False


class TransferChange(Change):
    owner_id: int = Field(gt=0)


class ActionChange(Change):
    next_action: str = Field(default="", max_length=500)


class OrdinaryChange(Change):
    description: str | None = Field(default=None, min_length=20, max_length=20000)
    next_action: str | None = Field(default=None, min_length=3, max_length=500)
    priority: str | None = None
    due_at: datetime | None = None


class ReviewChange(Change):
    decision: str


def parse(schema):
    try:
        return schema.model_validate(request.get_json(silent=True) or {})
    except ValidationError as error:
        abort(422, description="; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()))


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(422, description="A JSON object is required.")
    return data


def user_json(user):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "requested_role": user.requested_role, "organization": user.organization or "",
            "approval_pending": user.role == "pending",
            "bureau_id": user.bureau_id, "bureau": user.bureau.code if user.bureau else "Assigned scope",
            "roles": sorted(roles(user)), "capabilities": capabilities(user)}


def institution_json(inst):
    return {"id": inst.id, "name": inst.name, "external_id": inst.external_id,
            "verified": inst.verified, "region": inst.region, "address": inst.address}


def condition(case):
    if case.status == "disposed":
        return "closed"
    if case.paused_at:
        return "paused"
    if not case.due_at:
        return "not_set"
    due = case.due_at.replace(tzinfo=timezone.utc)
    return "overdue" if due < now() else "due_soon" if due <= now() + timedelta(days=2) else "on_track"


def case_json(case, detail=False):
    result = {"id": case.id, "reference": case.reference, "institution": institution_json(case.institution),
              "category": case.category, "priority": case.priority, "status": case.status,
              "bureau": case.bureau.code, "bureau_id": case.bureau_id, "owner": case.owner.name,
              "owner_id": case.owner_id, "received_at": iso(case.received_at), "due_at": iso(case.due_at),
              "deadline_condition": condition(case), "deadline_policy": case.deadline_policy,
              "deadline_config": case.deadline_config, "paused_at": iso(case.paused_at),
              "next_action": case.next_action, "version": case.version, "content_revision": case.content_revision,
              "matching_state": case.matching_state, "matching_error": case.matching_error}
    result.update(issue_summary=case.issue_summary, complainant_type=case.complainant_type,
                  source_channel=case.source_channel, source_reference=case.source_reference, entered_at=iso(case.entered_at))
    if detail:
        content = has_content(case)
        result["description"] = case.description if content else "Full complaint content is outside your appointment's field scope. Use the assigned proceeding records below."
        result["can_transition"] = allowed(case, "case.transition")
        result["allowed_transitions"] = TRANSITIONS[case.status] if result["can_transition"] else []
        result["can_edit"] = allowed(case, "case.edit")
        result["can_transfer"] = allowed(case, "case.transfer")
        result["can_route"] = allowed(case, "case.route")
        result["can_proceeding"] = allowed(case, "case.proceeding")
        result["can_compliance"] = allowed(case, "case.compliance")
        result["can_export"] = allowed(case, "case.export")
        result["can_read_documents"] = allowed(case, "documents.read")
        result["has_content"] = content
        if content:
            result.update(affected_person=case.affected_person, submitter_name=case.submitter_name,
                          representation_basis=case.representation_basis, prior_proceedings=case.prior_proceedings,
                          sensitivity=case.sensitivity, taxonomy_version=case.taxonomy_version)
    return result


def event(case, kind, summary, reason="", changes=None, actor=None):
    actor = actor or getattr(g, "user", None)
    item = ActionEvent(complaint_id=case.id if case else None, actor_id=actor.id if actor else None,
                       actor_name=actor.name if actor else "OneCase worker", bureau_id=case.bureau_id if case else None,
                       kind=kind, summary=summary, reason=reason, changes=changes or {}, request_id=getattr(g, "request_id", ""))
    db.session.add(item)
    return item


def event_json(item):
    return {"id": item.id, "complaint_id": item.complaint_id,
            "reference": item.complaint.reference if item.complaint else None, "actor": item.actor_name,
            "kind": item.kind, "summary": item.summary, "reason": item.reason,
            "changes": item.changes, "outcome": item.outcome, "severity": item.severity,
            "created_at": iso(item.created_at)}


def enqueue(case):
    key = f"matching:{case.id}:{case.content_revision}"
    if not db.session.scalar(select(Job).where(Job.dedup_key == key)):
        db.session.add(Job(complaint_id=case.id, revision=case.content_revision, dedup_key=key))
    case.matching_state = "queued"
    case.matching_error = None


def notify(user_id, case, kind, message, key):
    if not db.session.scalar(select(Notification.id).where(Notification.dedup_key == key)):
        db.session.add(Notification(user_id=user_id, complaint_id=case.id, kind=kind, message=message, dedup_key=key))


def filtered_cases(receipt_dates=True, aggregate=False):
    query = select(Complaint).join(Institution).where(scope(aggregate=aggregate))
    filters = request.args
    if filters.get("q"):
        term = "%" + filters["q"][:120] + "%"
        query = query.where(or_(Complaint.reference.ilike(term), Institution.name.ilike(term), Institution.external_id.ilike(term)))
    for key, column in [("bureau", Complaint.bureau_id), ("institution", Complaint.institution_id), ("status", Complaint.status),
                        ("category", Complaint.category), ("region", Institution.region)]:
        if filters.get(key):
            query = query.where(column == filters[key])
    for key, sign in ([("from", "start"), ("to", "end")] if receipt_dates else []):
        if filters.get(key):
            try:
                value = datetime.fromisoformat(filters[key]).replace(tzinfo=timezone.utc)
            except ValueError:
                abort(422, description="Invalid report date.")
            query = query.where(Complaint.received_at >= value) if sign == "start" else query.where(Complaint.received_at < value + timedelta(days=1))
    if filters.get("active") == "true":
        query = query.where(Complaint.status != "disposed")
    if filters.get("overdue") == "true":
        query = query.where(Complaint.status != "disposed", Complaint.due_at < now(), Complaint.paused_at.is_(None))
    return query


def page(query, serializer, model):
    try:
        limit = min(max(int(request.args.get("limit", 30)), 1), 100)
        cursor = int(request.args.get("cursor", 0))
    except ValueError:
        abort(422, description="Invalid pagination.")
    total = db.session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    query = query.where(model.id < cursor) if cursor else query
    records = db.session.scalars(query.limit(limit + 1)).all()
    return {"items": [serializer(item) for item in records[:limit]], "total": total,
            "nextCursor": records[limit - 1].id if len(records) > limit else None,
            "asOf": iso(now()), "filters": request.args.to_dict()}


@api.post("/auth/register")
def signup():
    from .auth import PUBLIC_ROLES, ROLES
    from .security import compromised_password
    data = parse(SignupInput)
    email = data.email.lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        abort(422, description="Enter a valid email address.")
    if data.account_type not in PUBLIC_ROLES | ROLES:
        abort(422, description="Choose a valid account type.")
    if data.password != data.confirm_password:
        abort(422, description="Passwords do not match.")
    if compromised_password(data.password):
        abort(422, description="Choose a password that is not on the compromised-password denylist.")
    if data.account_type in ROLES and len(data.organization) < 2:
        abort(422, description="Enter the organization for your staff access request.")
    if db.session.scalar(select(User.id).where(func.lower(User.email) == email)):
        abort(409, description="An account with this email already exists. Sign in instead.")
    # Staff signup records a request, never a privileged role or bureau grant.
    user = User(name=data.name, email=email, password_hash=hasher.hash(data.password),
                role=data.account_type if data.account_type in PUBLIC_ROLES else "pending",
                requested_role=data.account_type, organization=data.organization, bureau_id=None)
    db.session.add(user)
    db.session.flush()
    event(None, "account_registered", "Account registered", actor=user,
          changes={"requested_role": data.account_type, "approval_pending": user.role == "pending"})
    db.session.commit()
    return {"approval_pending": user.role == "pending",
            "message": "Account created. Sign in to view your access request." if user.role == "pending" else "Account created. You can now sign in."}, 201


@api.get("/account/summary")
@authenticated
def account_summary():
    cases = select(Complaint.id).where(scope())
    total = db.session.scalar(select(func.count()).select_from(cases.subquery()))
    active = db.session.scalar(select(func.count()).select_from(Complaint).where(scope(), Complaint.status != "disposed"))
    unread = db.session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == g.user.id, Notification.read_at.is_(None)))
    return {"total": total, "active": active, "closed": total - active, "unread_alerts": unread}


@api.post("/auth/login")
def login():
    data = parse(LoginInput)
    email, password = data.email.lower(), data.password
    key = digest(f"{request.remote_addr}:{email}")
    count = db.session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key == key, LoginAttempt.at > now() - timedelta(minutes=15)))
    if count >= 10:
        abort(429, description="Too many attempts. Try again in 15 minutes.")
    db.session.add(LoginAttempt(key=key))
    ip_key = digest("ip:" + str(request.remote_addr))
    ip_count = db.session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key == ip_key, LoginAttempt.at > now() - timedelta(minutes=15)))
    account_key = digest("account:" + email)
    account_count = db.session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key == account_key, LoginAttempt.at > now() - timedelta(minutes=15)))
    if ip_count >= 50 or account_count >= 15:
        abort(429, description="Too many attempts. Try again in 15 minutes.")
    db.session.add_all([LoginAttempt(key=ip_key), LoginAttempt(key=account_key)])
    db.session.commit()
    user = db.session.scalar(select(User).where(User.email == email, User.active.is_(True)).with_for_update())
    try:
        valid = hasher.verify(user.password_hash if user else DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not user or not valid:
        item = event(None, "authentication_failed", "Officer authentication failed")
        item.actor_name, item.outcome, item.severity = "Unauthenticated request", "denied", "warning"
        db.session.commit()
        abort(401, description="Email or password is incorrect.")
    from .security import verify_mfa
    if user.mfa_enabled and not verify_mfa(user, data.verification_code):
        return {"error": {"message": "Enter a valid authenticator or one-time recovery code.", "status": 403, "mfa_required": True}}, 403
    if current_app.config["APP_ENV"] == "production" and roles(user) & {"lead", "reviewer", "committee", "verifier", "admin"} and not user.mfa_enabled:
        abort(403, description="Privileged production access requires MFA enrollment through the approved administrator process.")
    old = request.cookies.get("onecase_session")
    if old and (old_session := db.session.get(Session, digest(old))):
        db.session.delete(old_session)
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.session.add(Session(id=digest(token), user_id=user.id, csrf=csrf, expires_at=now() + timedelta(hours=8)))
    event(None, "authenticated", "Officer sign-in completed", actor=user)
    db.session.commit()
    response = make_response({"user": user_json(user), "csrf": csrf})
    response.set_cookie("onecase_session", token, httponly=True, secure=current_app.config["COOKIE_SECURE"], samesite="Strict", max_age=28800)
    return response


@api.get("/auth/me")
@authenticated
def me():
    return {"user": user_json(g.user), "csrf": g.session.csrf}


@api.post("/auth/refresh")
@authenticated
def refresh():
    db.session.delete(g.session)
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.session.add(Session(id=digest(token), user_id=g.user.id, csrf=csrf, expires_at=g.session.expires_at, authenticated_at=g.session.authenticated_at))
    db.session.commit()
    response = make_response({"user": user_json(g.user), "csrf": csrf})
    response.set_cookie("onecase_session", token, httponly=True, secure=current_app.config["COOKIE_SECURE"], samesite="Strict", max_age=28800)
    return response


@api.post("/auth/logout")
@authenticated
def logout():
    db.session.delete(g.session)
    db.session.commit()
    response = make_response({"ok": True})
    response.delete_cookie("onecase_session")
    return response


@api.get("/directory")
@authenticated
def directory():
    from .auth import PUBLIC_ROLES
    if g.user.role in PUBLIC_ROLES:
        return {"bureaus": [], "officers": [], "participants": [], "categories": CATEGORIES, "deadline_rules": []}
    return {"bureaus": [{"id": x.id, "code": x.code, "name": x.name} for x in db.session.scalars(select(Bureau).order_by(Bureau.code))],
            "officers": [user_json(x) for x in db.session.scalars(select(User).where(User.active.is_(True), User.role.in_(["officer", "lead"])).order_by(User.name))],
            "participants": [user_json(x) for x in db.session.scalars(select(User).where(User.active.is_(True), User.role != "admin").order_by(User.name))],
            "categories": CATEGORIES,
            "deadline_rules": [{"id": "none", "name": "No automatic deadline"}, {"id": "demo-business-v1", "name": "Illustrative: 10 business days · Mon–Fri, 09–17 IST"}, {"id": "demo-elapsed-v1", "name": "Illustrative: 14 elapsed days"}]}


@api.get("/institutions")
@authenticated
def institutions():
    # Directory identity is public within the provisioned workspace; case counts remain scoped.
    query = select(Institution)
    if request.args.get("q"):
        term = "%" + request.args["q"][:120] + "%"
        query = query.where(or_(Institution.name.ilike(term), Institution.external_id.ilike(term)))
    return page(query.order_by(Institution.id.desc()), institution_json, Institution)


@api.get("/institutions/<int:item_id>")
@authenticated
def institution_detail(item_id):
    inst = db.session.get(Institution, item_id)
    if not inst:
        abort(404)
    return institution_json(inst)


@api.get("/institutions/<int:item_id>/complaints")
@authenticated
def institution_cases(item_id):
    return page(select(Complaint).where(scope(), Complaint.institution_id == item_id).order_by(Complaint.id.desc()), case_json, Complaint)


@api.get("/complaints")
@authenticated
def complaints():
    return page(filtered_cases().order_by(Complaint.id.desc()), case_json, Complaint)


@api.post("/complaints")
@authenticated
def register_case():
    if not roles() & {"officer", "lead"}:
        abort(403, description="Only officers may register complaints.")
    data = parse(Registration)
    if data.complainant_type not in ("student", "faculty", "staff", "other") or data.sensitivity not in ("standard", "restricted"):
        abort(422, description="Choose a valid complainant type and sensitivity.")
    if data.affected_person and data.submitter_name and data.affected_person != data.submitter_name and len(data.representation_basis) < 5:
        abort(422, description="Record the representative's authorization basis.")
    if data.source_channel in ("Import", "Portal reference") and not data.source_reference:
        abort(422, description="Imported/source-system complaints require their original reference.")
    if data.category not in CATEGORIES or data.priority not in ("low", "normal", "high", "urgent"):
        abort(422, description="Choose a valid category and priority.")
    if data.received_at > now() + timedelta(minutes=1):
        abort(422, description="Receipt date cannot be in the future.")
    if data.due_at and (data.due_at <= data.received_at or len(data.deadline_reason) < 5):
        abort(422, description="An explicit deadline must follow receipt and have a recorded reason.")
    if data.deadline_rule not in ("none", "demo-business-v1", "demo-elapsed-v1"):
        abort(422, description="Invalid deadline rule.")
    if data.due_at and data.deadline_rule != "none":
        abort(422, description="Choose either an illustrative rule or an explicit deadline.")
    institution = db.session.get(Institution, data.institution_id)
    owner = db.session.get(User, data.owner_id)
    if not institution or not owner or not owner.active or owner.bureau_id != g.user.bureau_id or owner.role not in ("officer", "lead"):
        abort(422, description="Select an institution and an active accountable officer in your bureau.")
    if "lead" not in roles() and owner.id != g.user.id:
        abort(403, description="Only a bureau lead may assign another officer.")
    key = request.headers.get("Idempotency-Key", "")
    if not 8 <= len(key) <= 100:
        abort(422, description="An Idempotency-Key of 8–100 characters is required.")
    payload_digest = digest(json.dumps(data.model_dump(mode="json"), sort_keys=True))
    previous = db.session.scalar(select(Idempotency).where(Idempotency.user_id == g.user.id, Idempotency.key == key))
    if previous:
        if previous.digest != payload_digest:
            abort(409, description="This submission key was already used for different content.")
        return case_json(case_or_404(previous.complaint_id), True), 200
    case = Complaint(reference=f"OC-{now().year}-{uuid4().hex[:10].upper()}", institution_id=institution.id,
                     category=data.category, description=data.description, priority=data.priority,
                     bureau_id=owner.bureau_id, owner_id=owner.id, received_at=data.received_at,
                     due_at=data.due_at, deadline_policy="Authorized explicit deadline v1" if data.due_at else "Deadline not set",
                     next_action=data.next_action)
    for field in ("issue_summary", "complainant_type", "affected_person", "submitter_name", "representation_basis", "source_channel", "source_reference", "prior_proceedings", "sensitivity"):
        setattr(case, field, getattr(data, field))
    db.session.add(case)
    if data.deadline_rule != "none":
        from .sla import calculate
        mode = "business" if data.deadline_rule == "demo-business-v1" else "elapsed"
        minutes = 10 * 8 * 60 if mode == "business" else 14 * 24 * 60
        case.deadline_config = {"mode": mode, "minutes": minutes, "version": data.deadline_rule, "timezone": "Asia/Kolkata", "holidays": [], "working_hours": "09:00–17:00", "weekdays": "Mon–Fri", "illustrative": True}
        case.due_at = calculate(data.received_at, minutes, mode)
        case.deadline_policy = f"Illustrative {mode} policy {data.deadline_rule}"
    elif data.due_at:
        case.deadline_config = {"mode": "elapsed", "minutes": (data.due_at - data.received_at).total_seconds() / 60, "version": "explicit-v1", "timezone": "Asia/Kolkata"}
    db.session.flush()
    db.session.add(Assignment(complaint_id=case.id, bureau_id=case.bureau_id, owner_id=case.owner_id, reason="Initial registration"))
    db.session.add(Idempotency(user_id=g.user.id, key=key, digest=payload_digest, complaint_id=case.id))
    event(case, "registered", "Complaint registered and intake acknowledged", data.deadline_reason,
          {"acknowledgement": {"reference": case.reference, "source_receipt_at": iso(case.received_at), "entry_at": iso(case.entered_at)}, "source_channel": case.source_channel})
    enqueue(case)
    db.session.commit()
    return case_json(case, True), 201


@api.get("/complaints/<int:case_id>")
@authenticated
def detail(case_id):
    case = case_or_404(case_id)
    result = case_json(case, True)
    result["attachments"] = [{"id": a.id, "filename": a.filename, "size": a.size, "checksum": a.checksum, "proceeding_id": a.proceeding_id, "scan_state": a.scan_state, "scan_detail": a.scan_detail} for a in db.session.scalars(select(Attachment).where(Attachment.complaint_id == case.id)) if document_allowed(case, a)]
    result["transfers"] = [{"id": t.id, "to_owner_id": t.to_owner_id, "created_at": iso(t.created_at), "acknowledged_at": iso(t.acknowledged_at)} for t in db.session.scalars(select(Transfer).where(Transfer.complaint_id == case.id).order_by(Transfer.id.desc()))]
    result["pauses"] = [{"id": p.id, "started_at": iso(p.started_at), "ended_at": iso(p.ended_at), "reason": p.reason} for p in db.session.scalars(select(SLAPause).where(SLAPause.complaint_id == case.id).order_by(SLAPause.id))]
    return result


@api.patch("/complaints/<int:case_id>")
@authenticated
def edit_case(case_id):
    case = case_or_404(case_id, write=True)
    data = parse(OrdinaryChange)
    check_version(case, data.version)
    changes = {}
    for field in ("description", "next_action", "priority", "due_at"):
        if field not in data.model_fields_set:
            continue
        value = getattr(data, field)
        if field != "due_at" and value is None:
            abort(422, description=f"{field} may not be null.")
        if field == "priority" and value not in ("low", "normal", "high", "urgent"):
            abort(422, description="Invalid priority.")
        if field == "due_at":
            if g.user.role != "lead":
                abort(403, description="Only a bureau lead may revise deadlines.")
            if value and (not value.tzinfo or value <= case.received_at.replace(tzinfo=timezone.utc)):
                abort(422, description="A timezone-aware deadline after receipt is required.")
            case.deadline_revision += 1
            case.deadline_policy = "Authorized explicit deadline v1"
            if case.paused_at:
                abort(422, description="Resume the SLA clock before revising the deadline.")
            case.deadline_config = {"mode": "elapsed", "minutes": (value - case.received_at.replace(tzinfo=timezone.utc)).total_seconds() / 60, "version": "explicit-v1", "timezone": "Asia/Kolkata"} if value else {}
        changes[field] = {"before": iso(getattr(case, field)) if field == "due_at" else ("Previous text" if field == "description" else getattr(case, field)),
                          "after": iso(value) if field == "due_at" else ("Revised text" if field == "description" else value)}
        setattr(case, field, value)
    if not changes:
        abort(422, description="No fields to update.")
    if "description" in changes:
        case.content_revision += 1
        enqueue(case)
    event(case, "updated", "Case details updated", data.reason, changes)
    case.version += 1
    db.session.commit()
    return case_json(case, True)


@api.post("/complaints/<int:case_id>/sla/<operation>")
@authenticated
def sla_clock(case_id, operation):
    case = case_or_404(case_id, write=True, lead=True)
    data = parse(Change)
    check_version(case, data.version)
    if not case.due_at or case.status == "disposed":
        abort(422, description="An active case with a deadline is required.")
    if operation == "pause":
        if case.paused_at:
            abort(409, description="The SLA clock is already paused.")
        case.paused_at = now()
        db.session.add(SLAPause(complaint_id=case.id, started_at=case.paused_at, reason=data.reason))
    elif operation == "resume":
        if not case.paused_at:
            abort(409, description="The SLA clock is not paused.")
        pause = db.session.scalar(select(SLAPause).where(SLAPause.complaint_id == case.id, SLAPause.ended_at.is_(None)))
        pause.ended_at = now()
        if case.deadline_config:
            from .sla import calculate
            pauses = db.session.scalars(select(SLAPause).where(SLAPause.complaint_id == case.id, SLAPause.ended_at.is_not(None))).all()
            case.due_at = calculate(case.received_at.replace(tzinfo=timezone.utc), case.deadline_config["minutes"], case.deadline_config["mode"], pauses=[(p.started_at.replace(tzinfo=timezone.utc), p.ended_at.replace(tzinfo=timezone.utc)) for p in pauses])
        else:
            case.due_at += now() - case.paused_at.replace(tzinfo=timezone.utc)
        case.paused_at = None
        case.deadline_revision += 1
    else:
        abort(404)
    case.version += 1
    event(case, f"sla_{operation}", f"SLA clock {operation} recorded", data.reason)
    db.session.commit()
    return case_json(case, True)


@api.post("/complaints/<int:case_id>/status")
@authenticated
def change_status(case_id):
    case = case_or_404(case_id, operation="case.transition")
    data = parse(StatusChange)
    check_version(case, data.version)
    if data.status not in TRANSITIONS[case.status]:
        abort(422, description="This status transition is not permitted.")
    if data.status == "disposed":
        from .workflow import validate_disposition
        validate_disposition(case, data)
    previous = case.status
    case.status = data.status
    event(case, "reopened" if previous == "disposed" else "status_changed", f"Status changed to {case.status.replace('_', ' ')}",
          data.reason, {"status": {"before": previous, "after": case.status}, "deadline_at": iso(case.due_at), "deadline_policy": case.deadline_policy, "paused_at": iso(case.paused_at),
                        "outcome_document_id": data.outcome_document_id, "communication": data.communication,
                        "external_proceedings_continue": data.external_continues, "verifier_id": g.user.id})
    db.session.commit()
    return case_json(case, True)


@api.post("/complaints/<int:case_id>/actions")
@authenticated
def add_action(case_id):
    case = case_or_404(case_id, write=True)
    data = parse(ActionChange)
    check_version(case, data.version)
    event(case, "action_recorded", "Officer action recorded", data.reason)
    if data.next_action:
        case.next_action = data.next_action
    case.version += 1
    db.session.commit()
    return case_json(case, True)


@api.post("/complaints/<int:case_id>/transfer")
@authenticated
def transfer(case_id):
    case = case_or_404(case_id, write=True, lead=True)
    data = parse(TransferChange)
    check_version(case, data.version)
    recipient = db.session.get(User, data.owner_id)
    if not recipient or not recipient.active or recipient.role not in ("officer", "lead") or not recipient.bureau_id or recipient.id == case.owner_id:
        abort(422, description="Choose a different active receiving officer.")
    old_owner, old_bureau = case.owner_id, case.bureau.code
    previous = db.session.scalar(select(Assignment).where(Assignment.complaint_id == case.id, Assignment.ended_at.is_(None)))
    if previous:
        previous.ended_at = now()
    db.session.add(Assignment(complaint_id=case.id, bureau_id=recipient.bureau_id, owner_id=recipient.id, reason=data.reason))
    receipt = Transfer(complaint_id=case.id, from_owner_id=old_owner, to_owner_id=recipient.id, actor_id=g.user.id, reason=data.reason)
    db.session.add(receipt)
    case.owner_id, case.bureau_id = recipient.id, recipient.bureau_id
    db.session.flush()
    event(case, "transferred", f"Transferred from {old_bureau} to {recipient.bureau.code}", data.reason,
          {"owner_id": {"before": old_owner, "after": recipient.id}})
    notify(recipient.id, case, "assignment", f"{case.reference} was assigned to you. Acknowledge receipt.", f"transfer:{receipt.id}:{recipient.id}")
    db.session.commit()
    # Return only the transfer receipt; sender access does not survive automatically.
    return {"id": receipt.id, "complaint_id": case.id, "reference": case.reference, "owner": recipient.name, "bureau": recipient.bureau.code}


@api.post("/transfers/<int:transfer_id>/acknowledge")
@authenticated
def acknowledge(transfer_id):
    item = db.session.get(Transfer, transfer_id)
    if not item or item.to_owner_id != g.user.id:
        abort(404)
    case = case_or_404(item.complaint_id, write=True)
    if not item.acknowledged_at:
        item.acknowledged_at = now()
        event(case, "acknowledged", "Receiving officer acknowledged transfer")
        case.version += 1
        db.session.commit()
    return {"ok": True}


@api.get("/complaints/<int:case_id>/actions")
@authenticated
def history(case_id):
    case_or_404(case_id)
    return page(select(ActionEvent).where(ActionEvent.complaint_id == case_id).order_by(ActionEvent.id.desc()), event_json, ActionEvent)


@api.post("/complaints/<int:case_id>/matching/retry")
@authenticated
def retry_matching(case_id):
    case = case_or_404(case_id, write=True)
    check_version(case, body().get("version"))
    job = db.session.scalar(select(Job).where(Job.dedup_key == f"matching:{case.id}:{case.content_revision}"))
    if job and job.state == "failed":
        job.state, job.attempts, job.available_at = "queued", 0, now()
    elif job and job.state in ("queued", "running"):
        return {"ok": True, "state": case.matching_state}
    else:
        enqueue(case)
    case.matching_state, case.matching_error = "queued", None
    db.session.commit()
    return {"ok": True, "state": "queued"}


@api.post("/complaints/<int:case_id>/attachments")
@authenticated
def upload(case_id):
    case = case_or_404(case_id)
    proceeding_id = request.form.get("proceeding_id", type=int)
    if proceeding_id:
        from .models import Proceeding
        proceeding = db.session.get(Proceeding, proceeding_id)
        if not proceeding or proceeding.complaint_id != case.id or not (proceeding_allowed(proceeding, "coordinate") or proceeding_allowed(proceeding, "contribute")):
            abort(403, description="A current proceeding appointment with evidence access is required.")
    elif not allowed(case, "case.edit"):
        abort(403, description="Proceeding participants must attach files to their assigned proceeding.")
    try:
        check_version(case, int(request.form.get("version", "0")))
    except ValueError:
        abort(422, description="Invalid case version.")
    item = request.files.get("file")
    if not item:
        abort(422, description="Choose a PDF, PNG or JPEG file.")
    content = item.read()
    if not content or len(content) > current_app.config["MAX_UPLOAD_BYTES"]:
        abort(422, description="Evidence exceeds the configured upload limit.")
    count = db.session.scalar(select(func.count()).select_from(Attachment).where(Attachment.complaint_id == case.id))
    if count >= current_app.config["DOCUMENT_LIMIT_PER_CASE"]:
        abort(429, description="This case has reached its evidence file limit.")
    media = "application/pdf" if content.startswith(b"%PDF-") else "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if content.startswith(b"\xff\xd8\xff") else None
    name = secure_filename(item.filename or "evidence")[:180]
    ext = Path(name).suffix.lower()
    if not media or ext not in {"application/pdf": [".pdf"], "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]}[media]:
        abort(422, description="File signature and extension must match PDF, PNG or JPEG.")
    key = uuid4().hex
    from . import storage
    storage_backend, storage_bucket = storage.put(key, content, media)
    try:
        sensitivity = request.form.get("sensitivity", "standard")
        if sensitivity not in ("standard", "restricted"):
            abort(422, description="Invalid evidence sensitivity.")
        db.session.add(Attachment(complaint_id=case.id, filename=name, key=key, media_type=media, size=len(content), checksum=hashlib.sha256(content).hexdigest(), proceeding_id=proceeding_id, sensitivity=sensitivity, storage_backend=storage_backend, storage_bucket=storage_bucket))
        event(case, "evidence_added", f"Evidence added: {name}")
        case.version += 1
        db.session.commit()
    except Exception:
        storage.remove(key, storage_backend, storage_bucket)
        raise
    return {"ok": True}, 201


@api.get("/attachments/<int:attachment_id>/download")
@authenticated
def download(attachment_id):
    attachment = db.session.get(Attachment, attachment_id)
    if not attachment:
        abort(404)
    case = case_or_404(attachment.complaint_id)
    if not document_allowed(case, attachment):
        abort(404, description="Document unavailable in your field scope.")
    if attachment.scan_state != "clean":
        abort(423, description="Evidence is quarantined pending validation and malware checks.")
    from .storage import read
    try:
        content = read(attachment)
    except FileNotFoundError:
        abort(404, description="Evidence file unavailable.")
    event(case, "evidence_downloaded", "Authorized evidence download", changes={"attachment_id": attachment.id})
    db.session.commit()
    return send_file(io.BytesIO(content), as_attachment=True, download_name=attachment.filename, mimetype=attachment.media_type)


def authorized_pairs():
    ids = [c.id for c in db.session.scalars(select(Complaint).where(scope())) if has_content(c)]
    return select(Pair).where(Pair.case_a_id.in_(ids), Pair.case_b_id.in_(ids))


def pair_json(pair, detailed=False):
    result = {"id": pair.id, "a": case_json(pair.a, detailed), "b": case_json(pair.b, detailed),
              "state": pair.state, "band": pair.band, "evidence": pair.evidence, "version": pair.version}
    result["stale"] = pair.evidence.get("revisions") != {str(pair.a.id): pair.a.content_revision, str(pair.b.id): pair.b.content_revision}
    if detailed:
        result["can_review"] = "reviewer" in roles()
        result["reviews"] = [{"id": x.id, "reviewer": x.user.name, "decision": x.decision, "reason": x.reason, "created_at": iso(x.created_at)} for x in db.session.scalars(select(Review).where(Review.pair_id == pair.id).order_by(Review.id.desc()))]
    return result


@api.get("/overlaps")
@authenticated
def overlaps():
    query = authorized_pairs().where(or_(Pair.band != "low", Pair.state != "pending"))
    if request.args.get("state"):
        query = query.where(Pair.state == request.args["state"])
    cohort = filtered_cases().with_only_columns(Complaint.id)
    query = query.where(or_(Pair.case_a_id.in_(cohort), Pair.case_b_id.in_(cohort)))
    return page(query.order_by(Pair.id.desc()), pair_json, Pair)


@api.get("/overlaps/<int:pair_id>")
@authenticated
def overlap_detail(pair_id):
    pair = db.session.scalar(authorized_pairs().where(Pair.id == pair_id))
    if not pair:
        abort(404)
    return pair_json(pair, True)


@api.post("/overlaps/<int:pair_id>/review")
@authenticated
def review(pair_id):
    if "reviewer" not in roles():
        abort(403, description="A designated reviewer must record the decision.")
    pair = db.session.scalar(authorized_pairs().where(Pair.id == pair_id))
    if not pair:
        abort(404)
    data = parse(ReviewChange)
    check_version(pair, data.version)
    if data.decision not in ("related", "unrelated"):
        abort(422, description="Choose related or unrelated.")
    if pair_json(pair)["stale"]:
        abort(409, description="Case content changed after matching. Wait for fresh evidence before reviewing.")
    pair.state = data.decision
    pair.version += 1
    db.session.add(Review(pair_id=pair.id, user_id=g.user.id, decision=data.decision, reason=data.reason, revisions=pair.evidence["revisions"]))
    for case in (pair.a, pair.b):
        event(case, "overlap_reviewed", f"Possible overlap marked {data.decision}", data.reason, {"pair_id": pair.id})
    db.session.commit()
    return pair_json(pair, True)


@api.get("/notifications")
@authenticated
def notifications():
    visible = select(Complaint.id).where(scope())
    query = select(Notification).where(Notification.user_id == g.user.id, or_(Notification.complaint_id.is_(None), Notification.complaint_id.in_(visible)))
    def serialize(item):
        return {"id": item.id, "kind": item.kind, "message": item.message, "complaint_id": item.complaint_id,
                "read_at": iso(item.read_at), "created_at": iso(item.created_at)}
    return page(query.order_by(Notification.id.desc()), serialize, Notification)


@api.patch("/notifications/<int:item_id>")
@authenticated
def read_notification(item_id):
    item = db.session.get(Notification, item_id)
    if not item or item.user_id != g.user.id:
        abort(404)
    item.read_at = now()
    db.session.commit()
    return {"ok": True}


@api.get("/audit-logs")
@authenticated
def audit():
    visible = filtered_cases().with_only_columns(Complaint.id)
    query = select(ActionEvent).where(or_(ActionEvent.complaint_id.in_(visible), and_(ActionEvent.complaint_id.is_(None), ActionEvent.actor_id == g.user.id)))
    if request.args.get("kind"):
        query = query.where(ActionEvent.kind.in_(request.args["kind"].split(",")))
    if request.args.get("actor"):
        query = query.where(ActionEvent.actor_name.ilike("%" + request.args["actor"][:120] + "%"))
    return page(query.order_by(ActionEvent.id.desc()), event_json, ActionEvent)


def attention_key(case):
    priority = {"urgent": 3, "high": 2, "normal": 1, "low": 0}
    urgency = {"overdue": 3, "due_soon": 2, "on_track": 1, "not_set": 0, "paused": 0}
    return (-urgency.get(condition(case), 0), -priority[case.priority], iso(case.due_at) or "9999", iso(case.received_at), case.id)


@api.get("/dashboard/summary")
@authenticated
def dashboard():
    cases = db.session.scalars(filtered_cases()).all()
    active = [c for c in cases if c.status != "disposed"]
    ids = [c.id for c in cases]
    pairs = db.session.scalars(authorized_pairs().where(or_(Pair.case_a_id.in_(ids), Pair.case_b_id.in_(ids)))).all()
    visible_ids = filtered_cases(receipt_dates=False).with_only_columns(Complaint.id)
    # Throughput uses event-period boundaries independently of the receipt-cohort cards.
    from zoneinfo import ZoneInfo
    local = now().astimezone(ZoneInfo("Asia/Kolkata"))
    week = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    trend = []
    for offset in range(7, -1, -1):
        start, end = week - timedelta(weeks=offset), week - timedelta(weeks=offset - 1)
        received = db.session.scalar(select(func.count()).select_from(filtered_cases().where(Complaint.received_at >= start, Complaint.received_at < end).subquery()))
        disposed = db.session.scalar(select(func.count()).select_from(ActionEvent).where(ActionEvent.complaint_id.in_(visible_ids), ActionEvent.kind == "status_changed", ActionEvent.changes["status"]["after"].as_string() == "disposed", ActionEvent.created_at >= start, ActionEvent.created_at < end))
        trend.append({"week": start.strftime("%d %b"), "received": received, "disposed": disposed})
    recent = db.session.scalars(select(ActionEvent).where(ActionEvent.complaint_id.in_(ids)).order_by(ActionEvent.id.desc()).limit(6)).all()
    return {"total": len(cases), "active": len(active), "overdue": sum(condition(c) == "overdue" for c in active),
            "pending_pairs": sum(p.state == "pending" and p.band != "low" for p in pairs),
            "confirmed_pairs": sum(p.state == "related" for p in pairs),
            "attention": [case_json(c) for c in sorted(active, key=attention_key)[:6]],
            "recent": [event_json(e) for e in recent], "trend": trend, "asOf": iso(now()),
            "ageing": [{"label": label, "count": sum(low <= (now() - c.received_at.replace(tzinfo=timezone.utc)).days < high for c in active)} for label, low, high in [("0–7 days", 0, 8), ("8–30 days", 8, 31), ("31–60 days", 31, 61), ("61+ days", 61, 100000)]],
            "matching": {"queued": sum(c.matching_state == "queued" for c in cases), "failed": sum(c.matching_state == "failed" for c in cases)},
            "policy": "Demonstration policies only. Deadlines are illustrative or explicitly authorized."}


@api.get("/reports/complaints.csv")
@authenticated
def export():
    permitted = [c for c in db.session.scalars(filtered_cases().order_by(Complaint.id)) if allowed(c, "case.export")]
    if not permitted and db.session.scalar(filtered_cases().limit(1)):
        abort(403, description="A separate export grant is required for these records.")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reference", "Institution", "Category", "Status", "Bureau", "Owner", "Received UTC", "Due UTC", "Deadline condition"])
    def safe(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for case in permitted:
        writer.writerow([safe(v) for v in [case.reference, case.institution.name, case.category, case.status, case.bureau.code, case.owner.name, iso(case.received_at), iso(case.due_at), condition(case)]])
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="onecase-complaints.csv"'
    event(None, "exported", "Scoped complaint register exported", changes={"record_count": len(permitted)})
    db.session.commit()
    return response


@api.get("/reports/metrics")
@authenticated
def report_metrics():
    cohort = filtered_cases().with_only_columns(Complaint.id)
    events = db.session.scalars(select(ActionEvent).where(ActionEvent.complaint_id.in_(cohort)).order_by(ActionEvent.created_at, ActionEvent.id)).all()
    starts, episodes = {}, []
    for item in events:
        if item.kind in ("registered", "reopened"):
            starts[item.complaint_id] = item.created_at
        if item.kind == "status_changed" and item.changes.get("status", {}).get("after") == "disposed":
            start = starts.pop(item.complaint_id, None)
            if start:
                hours = (item.created_at - start).total_seconds() / 3600
                deadline = item.changes.get("deadline_at")
                compliant = item.created_at.replace(tzinfo=timezone.utc) <= datetime.fromisoformat(deadline) if deadline and not item.changes.get("paused_at") else None
                episodes.append({"case_id": item.complaint_id, "hours": round(hours, 2), "compliant": compliant})
    eligible = [e for e in episodes if e["compliant"] is not None]
    return {"disposed_episodes": len(episodes), "mean_resolution_hours": round(sum(e["hours"] for e in episodes) / len(episodes), 2) if episodes else None,
            "sla_eligible_episodes": len(eligible), "sla_excluded_episodes": len(episodes) - len(eligible),
            "sla_compliance": sum(e["compliant"] for e in eligible) / len(eligible) if eligible else None,
            "definition": "Completed lifecycle episodes in the selected receipt cohort. SLA uses the deadline snapshot recorded at disposal; missing historical snapshots and actively paused clocks are excluded. Reopened episodes are counted separately.", "asOf": iso(now())}


@api.get("/operations")
@authenticated
def operations():
    require_admin()
    counts = {state: db.session.scalar(select(func.count()).select_from(Job).where(Job.state == state)) for state in ("queued", "running", "failed", "completed", "superseded")}
    oldest = db.session.scalar(select(func.min(Job.available_at)).where(Job.state == "queued"))
    return {"jobs": counts, "oldest_queued_at": iso(oldest), "asOf": iso(now())}
