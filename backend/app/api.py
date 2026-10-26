import csv
import hashlib
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from flask import Blueprint, abort, current_app, g, jsonify, make_response, request, send_file
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import and_, func, or_, select, update
from werkzeug.utils import secure_filename
from .auth import authenticated, case_or_404, check_version, digest, scope
from .models import (db, now, iso, User, Bureau, Institution, Complaint, Session, LoginAttempt,
                     Assignment, Transfer, ActionEvent, Notification, Attachment, Job,
                     Pair, Review, Idempotency, MatchingRun, SLAPause, AccountRequest,
                     OTPChallenge, AccountLockout)
from .email_service import (generate_otp, compute_otp_verifier, verify_otp_verifier,
                            mask_email, send_otp_email, get_smtp_config)

api = Blueprint("api", __name__)
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash("not-a-real-account-secret")
CATEGORIES = ["Fee refund", "Admissions", "Infrastructure", "Faculty", "Examination", "Other"]
TRANSITIONS = {"received": ["under_review", "disposed"], "under_review": ["awaiting_information", "disposed"],
               "awaiting_information": ["under_review", "disposed"], "disposed": ["under_review"]}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


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


class InstitutionCreate(Input):
    name: str = Field(min_length=3, max_length=200)
    external_id: str | None = Field(default=None, max_length=60)
    region: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=5, max_length=300)
    verified: bool = False


class UserProvision(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    role: str
    bureau_id: int | None = None
    password: str = Field(min_length=12, max_length=128)


class StudentRegistration(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=8, max_length=128)
    college_name: str = Field(min_length=2, max_length=200)
    roll_number: str = Field(min_length=1, max_length=60)
    department: str = Field(min_length=2, max_length=100)
    academic_year: str = Field(min_length=2, max_length=30)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.strip().lower()


class CollegeRepRegistration(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=8, max_length=128)
    college_name: str = Field(min_length=2, max_length=200)
    employee_id: str | None = Field(default=None, max_length=60)
    designation: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.strip().lower()


class OfficerAccountRequestInput(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    password: str = Field(min_length=8, max_length=128)
    employee_id: str | None = Field(default=None, max_length=60)
    designation: str = Field(min_length=2, max_length=100)
    bureau_code: str = Field(min_length=2, max_length=30)
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.strip().lower()


class AccountRequestReview(Input):
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(default="", max_length=2000)


class OTPVerifyInput(Input):
    challenge_id: str = Field(min_length=10, max_length=64)
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class OTPResendInput(Input):
    challenge_id: str = Field(min_length=10, max_length=64)


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
            "bureau_id": user.bureau_id, "bureau": user.bureau.code if user.bureau else "Explicit scope"}


def account_request_json(req):
    return {
        "id": req.id,
        "request_type": req.request_type,
        "name": req.name,
        "email": req.email,
        "college_name": req.college_name,
        "institution_id": req.institution_id,
        "institution_name": req.institution.name if req.institution else req.college_name,
        "roll_number": req.roll_number,
        "department": req.department,
        "academic_year": req.academic_year,
        "employee_id": req.employee_id,
        "designation": req.designation,
        "bureau_code": req.bureau_code,
        "reason": req.reason,
        "status": req.status,
        "created_at": iso(req.created_at),
        "reviewed_at": iso(req.reviewed_at),
        "reviewer_id": req.reviewer_id,
        "reviewer_name": req.reviewer.name if req.reviewer else None,
        "reviewer_decision_reason": req.reviewer_decision_reason,
        "user_id": req.user_id,
    }


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
    if detail:
        result["description"] = case.description
        result["allowed_transitions"] = TRANSITIONS[case.status]
        result["can_edit"] = g.user.role == "lead" and case.bureau_id == g.user.bureau_id or g.user.role == "officer" and case.owner_id == g.user.id
        result["can_transfer"] = g.user.role == "lead" and case.bureau_id == g.user.bureau_id
    return result


def event(case, kind, summary, reason="", changes=None, actor=None):
    actor = actor or getattr(g, "user", None)
    item = ActionEvent(complaint_id=case.id if case else None, actor_id=actor.id if actor else None,
                       actor_name=actor.name if actor else "OneCase worker", bureau_id=case.bureau_id if case else None,
                       kind=kind, summary=summary, reason=reason, changes=changes or {})
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


def filtered_cases(receipt_dates=True):
    query = select(Complaint).join(Institution).where(scope())
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
        query = query.where(Complaint.status != "disposed", Complaint.due_at < now())
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


@api.post("/auth/login")
def login():
    data = body()
    email = str(data.get("email", "")).strip().lower()[:180]
    password = str(data.get("password", ""))

    # IP rate limit: 10 attempts in 15 minutes per IP:email
    key = digest(f"{request.remote_addr}:{email}")
    count = db.session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key == key, LoginAttempt.at > now() - timedelta(minutes=15)))
    if count >= 10:
        abort(429, description="Too many attempts. Try again in 15 minutes.")
    db.session.add(LoginAttempt(key=key))
    db.session.commit()

    # Enforce 3-failed-password-attempts 60-second temporary lockout
    lockout = db.session.scalar(select(AccountLockout).where(AccountLockout.email == email).with_for_update())
    if lockout and lockout.locked_until:
        locked_time = lockout.locked_until.replace(tzinfo=timezone.utc) if lockout.locked_until.tzinfo is None else lockout.locked_until
        if locked_time > now():
            remaining = int((locked_time - now()).total_seconds())
            remaining = max(1, remaining)
            abort(429, description=f"Account temporarily locked due to 3 consecutive failed password attempts. Try again in {remaining} seconds.")
        else:
            lockout.failed_attempts = 0
            lockout.locked_until = None
            db.session.commit()

    user = db.session.scalar(select(User).where(User.email == email, User.active.is_(True)))
    try:
        valid = hasher.verify(user.password_hash if user else DUMMY_HASH, password[:1024])
    except (VerificationError, InvalidHashError):
        valid = False

    if not user or not valid:
        # Record failed attempt in AccountLockout for existing accounts
        if user:
            if not lockout:
                lockout = AccountLockout(email=email, failed_attempts=1, last_attempt_at=now())
                db.session.add(lockout)
            else:
                lockout.failed_attempts += 1
                lockout.last_attempt_at = now()
            event(None, "login_failed", f"Failed password attempt for user {user.id}", reason="Incorrect password", actor=user)
            if lockout.failed_attempts >= 3:
                lockout.locked_until = now() + timedelta(seconds=60)
                event(None, "account_locked", f"Temporary 60-second account lockout triggered for user {user.id}", reason="3 consecutive failed password attempts", actor=user)
            db.session.commit()

        # Check pending/rejected account requests
        pending_req = db.session.scalar(select(AccountRequest).where(AccountRequest.email == email).order_by(AccountRequest.created_at.desc()))
        if pending_req:
            try:
                req_valid = hasher.verify(pending_req.password_hash, password[:1024])
            except (VerificationError, InvalidHashError):
                req_valid = False
            if req_valid:
                if pending_req.status == "pending":
                    abort(403, description="Your account request is pending administrative verification. Access will be enabled once approved by an administrator.")
                elif pending_req.status == "rejected":
                    reason_msg = f" Reason: {pending_req.reviewer_decision_reason}" if pending_req.reviewer_decision_reason else ""
                    abort(403, description=f"Your account request was reviewed and rejected.{reason_msg}")

        if lockout and lockout.locked_until:
            locked_time = lockout.locked_until.replace(tzinfo=timezone.utc) if lockout.locked_until.tzinfo is None else lockout.locked_until
            if locked_time > now():
                abort(429, description="Too many failed password attempts. Account locked for 60 seconds.")
        abort(401, description="Email or password is incorrect.")


    # Password is correct: clear failed attempts
    if lockout:
        lockout.failed_attempts = 0
        lockout.locked_until = None
        lockout.last_attempt_at = now()

    # Invalidate prior pending challenges for this user
    prior_challenges = db.session.scalars(
        select(OTPChallenge).where(OTPChallenge.user_id == user.id, OTPChallenge.status == "pending")
    ).all()
    for ch in prior_challenges:
        ch.status = "invalidated"

    # Rate limiting on OTP generation (maximum 5 OTP emails per 15 minutes)
    recent_otp_count = db.session.scalar(
        select(func.count()).select_from(OTPChallenge).where(
            OTPChallenge.user_id == user.id,
            OTPChallenge.created_at > now() - timedelta(minutes=15)
        )
    )
    if recent_otp_count >= 5:
        abort(429, description="Too many verification requests. Please wait 15 minutes before trying again.")

    # Generate 6-digit cryptographic OTP and create challenge
    cfg = get_smtp_config()
    otp = generate_otp()
    salt = secrets.token_hex(16)
    secret_key = current_app.config.get("SECRET_KEY", "onecase-default-secret-key-32b")
    verifier = compute_otp_verifier(secret_key, salt, otp)
    expiry_minutes = cfg["expiry_minutes"]
    challenge = OTPChallenge(
        id=secrets.token_urlsafe(32),
        user_id=user.id,
        email=user.email,
        otp_verifier=verifier,
        salt=salt,
        expires_at=now() + timedelta(minutes=expiry_minutes),
        attempts=0,
        max_attempts=cfg["max_attempts"],
        status="pending",
        created_at=now(),
        ip_address=request.remote_addr
    )
    db.session.add(challenge)
    db.session.flush()

    # Deliver OTP email via Gmail SMTP
    success, err_msg = send_otp_email(user.email, otp, expiry_minutes=expiry_minutes)
    if not success:
        db.session.rollback()
        abort(503, description=err_msg or "Failed to deliver verification code. Please check configuration.")

    event(None, "otp_challenge_created", f"OTP challenge initiated for user {user.id}", reason="MFA verification challenge issued", actor=user)
    db.session.commit()
    # Critical: Do NOT create a session or set a session cookie here.
    return jsonify({
        "otp_required": True,
        "challenge_id": challenge.id,
        "email": mask_email(user.email),
        "expires_in": expiry_minutes * 60,
        "message": f"Verification code sent to {mask_email(user.email)}."
    })


@api.post("/auth/otp/verify")
def verify_otp_endpoint():
    data = parse(OTPVerifyInput)
    challenge_id = data.challenge_id.strip()
    otp = data.otp.strip()

    # Concurrency control with row lock
    challenge = db.session.scalar(
        select(OTPChallenge).where(OTPChallenge.id == challenge_id).with_for_update()
    )
    if not challenge:
        abort(404, description="Invalid or expired verification session. Please sign in again.")

    if challenge.status == "consumed":
        abort(400, description="This verification code has already been used.")

    if challenge.status != "pending":
        abort(400, description="This verification code is no longer valid. Please sign in again.")

    exp = challenge.expires_at.replace(tzinfo=timezone.utc) if challenge.expires_at.tzinfo is None else challenge.expires_at
    if exp <= now():
        challenge.status = "expired"
        db.session.commit()
        abort(400, description="Verification code has expired. Please request a new code.")

    if challenge.attempts >= challenge.max_attempts:
        challenge.status = "invalidated"
        db.session.commit()
        abort(429, description="Too many incorrect attempts. This code has been invalidated. Please sign in again.")

    secret_key = current_app.config.get("SECRET_KEY", "onecase-default-secret-key-32b")
    is_valid = verify_otp_verifier(secret_key, challenge.salt, otp, challenge.otp_verifier)

    if not is_valid:
        challenge.attempts += 1
        remaining = max(0, challenge.max_attempts - challenge.attempts)
        event(None, "otp_verify_failed", f"Incorrect OTP entered for user {challenge.user_id}", reason=f"Attempt {challenge.attempts}/{challenge.max_attempts}", actor=challenge.user)
        if challenge.attempts >= challenge.max_attempts:
            challenge.status = "invalidated"
            event(None, "otp_challenge_invalidated", f"OTP challenge invalidated for user {challenge.user_id}", reason="Exceeded maximum failed OTP attempts", actor=challenge.user)
            db.session.commit()
            abort(429, description="Too many incorrect attempts. This code has been invalidated. Please sign in again.")
        db.session.commit()
        abort(401, description=f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.")

    # OTP is valid: Atomically consume challenge to prevent race conditions
    affected = db.session.execute(
        update(OTPChallenge)
        .where(
            OTPChallenge.id == challenge_id,
            OTPChallenge.status == "pending"
        )
        .values(
            status="consumed",
            consumed_at=now()
        )
    ).rowcount

    if affected == 0:
        db.session.rollback()
        abort(400, description="This verification code has already been used.")

    user = challenge.user
    if not user or not user.active:
        db.session.commit()
        abort(403, description="This account is inactive or disabled.")

    # Rotate / delete old session
    old = request.cookies.get("onecase_session")
    if old and (old_session := db.session.get(Session, digest(old))):
        db.session.delete(old_session)

    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.session.add(Session(id=digest(token), user_id=user.id, csrf=csrf, expires_at=now() + timedelta(hours=8)))
    event(None, "login_success", f"User {user.email} successfully authenticated via OTP MFA", reason="Completed password and OTP verification", actor=user)
    db.session.commit()

    response = make_response({"user": user_json(user), "csrf": csrf})
    response.set_cookie(
        "onecase_session", token,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite="Strict",
        max_age=28800
    )
    return response


@api.post("/auth/otp/resend")
def resend_otp_endpoint():
    data = parse(OTPResendInput)
    challenge_id = data.challenge_id.strip()

    challenge = db.session.scalar(
        select(OTPChallenge).where(OTPChallenge.id == challenge_id).with_for_update()
    )
    if not challenge:
        abort(404, description="Verification session not found. Please sign in again.")

    if challenge.status == "consumed":
        abort(400, description="This verification session has already been completed.")

    cfg = get_smtp_config()
    cooldown = cfg["resend_cooldown"]

    created = challenge.created_at.replace(tzinfo=timezone.utc) if challenge.created_at.tzinfo is None else challenge.created_at
    elapsed = (now() - created).total_seconds()
    if elapsed < cooldown:
        wait_seconds = max(1, int(cooldown - elapsed))
        abort(429, description=f"Please wait {wait_seconds} seconds before requesting a new code.")

    recent_count = db.session.scalar(
        select(func.count()).select_from(OTPChallenge).where(
            OTPChallenge.user_id == challenge.user_id,
            OTPChallenge.created_at > now() - timedelta(minutes=15)
        )
    )
    if recent_count >= 5:
        abort(429, description="Too many verification requests. Please wait 15 minutes before trying again.")

    # Invalidate previous challenge
    challenge.status = "invalidated"

    otp = generate_otp()
    salt = secrets.token_hex(16)
    secret_key = current_app.config.get("SECRET_KEY", "onecase-default-secret-key-32b")
    verifier = compute_otp_verifier(secret_key, salt, otp)
    expiry_minutes = cfg["expiry_minutes"]

    new_challenge = OTPChallenge(
        id=secrets.token_urlsafe(32),
        user_id=challenge.user_id,
        email=challenge.email,
        otp_verifier=verifier,
        salt=salt,
        expires_at=now() + timedelta(minutes=expiry_minutes),
        attempts=0,
        max_attempts=cfg["max_attempts"],
        status="pending",
        created_at=now(),
        ip_address=request.remote_addr
    )
    db.session.add(new_challenge)
    db.session.flush()

    success, err_msg = send_otp_email(challenge.email, otp, expiry_minutes=expiry_minutes)
    if not success:
        db.session.rollback()
        abort(503, description=err_msg or "Failed to deliver verification code. Please check configuration.")

    event(None, "otp_challenge_resend", f"New OTP challenge generated for user {challenge.user_id}", reason="User requested OTP resend", actor=challenge.user)
    db.session.commit()
    return jsonify({
        "ok": True,
        "challenge_id": new_challenge.id,
        "email": mask_email(challenge.email),
        "expires_in": expiry_minutes * 60,
        "message": f"A new verification code has been sent to {mask_email(challenge.email)}."
    })



@api.get("/auth/me")
@authenticated
def me():
    return {"user": user_json(g.user), "csrf": g.session.csrf}


@api.post("/auth/refresh")
@authenticated
def refresh():
    db.session.delete(g.session)
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.session.add(Session(id=digest(token), user_id=g.user.id, csrf=csrf, expires_at=now() + timedelta(hours=8)))
    db.session.commit()
    response = make_response({"user": user_json(g.user), "csrf": csrf})
    response.set_cookie("onecase_session", token, httponly=True, secure=current_app.config["COOKIE_SECURE"], samesite="Strict", max_age=28800)
    return response


@api.post("/auth/logout")
@authenticated
def logout():
    event(None, "logout", f"User {g.user.email} signed out", reason="User initiated session termination", actor=g.user)
    db.session.delete(g.session)
    db.session.commit()
    response = make_response({"ok": True})
    response.delete_cookie("onecase_session")
    return response


@api.get("/directory")
@authenticated
def directory():
    return {"bureaus": [{"id": x.id, "code": x.code, "name": x.name} for x in db.session.scalars(select(Bureau).order_by(Bureau.code))],
            "officers": [user_json(x) for x in db.session.scalars(select(User).where(User.active.is_(True), User.role.in_(["officer", "lead"])).order_by(User.name))],
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


@api.post("/institutions")
@authenticated
def register_institution():
    if g.user.role not in ("admin", "lead", "officer"):
        abort(403, description="Only authorized personnel may register institutions.")
    data = parse(InstitutionCreate)
    if data.external_id:
        existing = db.session.scalar(select(Institution).where(Institution.external_id == data.external_id.strip()))
        if existing:
            abort(409, description="An institution with this AICTE identifier already exists.")
    inst = Institution(
        name=data.name.strip(),
        external_id=data.external_id.strip() if data.external_id else None,
        region=data.region.strip(),
        address=data.address.strip(),
        verified=data.verified and g.user.role in ("admin", "lead")
    )
    db.session.add(inst)
    db.session.commit()
    return institution_json(inst), 201


@api.post("/users/provision")
@authenticated
def provision_user_account():
    if g.user.role != "admin":
        abort(403, description="Only an administrator may provision user accounts.")
    data = parse(UserProvision)
    if data.role not in ("officer", "lead", "reviewer", "auditor", "executive", "admin"):
        abort(422, description="Invalid role.")
    bureau = None
    if data.role in ("officer", "lead"):
        if not data.bureau_id or not db.session.get(Bureau, data.bureau_id):
            abort(422, description="Officers and leads must be assigned to an active bureau.")
    existing = db.session.scalar(select(User).where(User.email == data.email.strip().lower()))
    if existing:
        abort(409, description="A user with this email address already exists.")
    user = User(
        name=data.name.strip(),
        email=data.email.strip().lower(),
        role=data.role,
        bureau_id=data.bureau_id if data.role in ("officer", "lead") else None,
        password_hash=hasher.hash(data.password),
        active=True
    )
    db.session.add(user)
    db.session.commit()
    return user_json(user), 201


def check_duplicate_account_request(email: str):
    existing_user = db.session.scalar(select(User).where(User.email == email))
    if existing_user:
        abort(409, description="An account with this email address already exists. Please sign in.")
    existing_req = db.session.scalar(select(AccountRequest).where(AccountRequest.email == email, AccountRequest.status == "pending"))
    if existing_req:
        abort(409, description="An account request for this email address is already pending administrative verification.")


@api.post("/account-requests/student")
def register_student():
    data = parse(StudentRegistration)
    check_duplicate_account_request(data.email)
    inst = db.session.scalar(select(Institution).where(Institution.name.ilike(data.college_name.strip())))
    req = AccountRequest(
        request_type="student",
        name=data.name.strip(),
        email=data.email,
        password_hash=hasher.hash(data.password),
        college_name=data.college_name.strip(),
        institution_id=inst.id if inst else None,
        roll_number=data.roll_number.strip(),
        department=data.department.strip(),
        academic_year=data.academic_year.strip(),
        status="pending"
    )
    db.session.add(req)
    db.session.commit()
    return jsonify({
        "ok": True,
        "id": req.id,
        "status": "pending",
        "message": "Student registration request submitted successfully. It is now pending administrative verification."
    }), 201


@api.post("/account-requests/college-rep")
def register_college_rep():
    data = parse(CollegeRepRegistration)
    check_duplicate_account_request(data.email)
    inst = db.session.scalar(select(Institution).where(Institution.name.ilike(data.college_name.strip())))
    req = AccountRequest(
        request_type="college_rep",
        name=data.name.strip(),
        email=data.email,
        password_hash=hasher.hash(data.password),
        college_name=data.college_name.strip(),
        institution_id=inst.id if inst else None,
        employee_id=data.employee_id.strip() if data.employee_id else None,
        designation=data.designation.strip(),
        reason=data.reason.strip(),
        status="pending"
    )
    db.session.add(req)
    db.session.commit()
    return jsonify({
        "ok": True,
        "id": req.id,
        "status": "pending",
        "message": "College representative access request submitted successfully. It is now pending administrative verification."
    }), 201


@api.post("/account-requests/officer")
def register_officer():
    data = parse(OfficerAccountRequestInput)
    check_duplicate_account_request(data.email)
    req = AccountRequest(
        request_type="officer",
        name=data.name.strip(),
        email=data.email,
        password_hash=hasher.hash(data.password),
        employee_id=data.employee_id.strip() if data.employee_id else None,
        designation=data.designation.strip(),
        bureau_code=data.bureau_code.strip().upper(),
        reason=data.reason.strip(),
        status="pending"
    )
    db.session.add(req)
    db.session.commit()
    return jsonify({
        "ok": True,
        "id": req.id,
        "status": "pending",
        "message": "AICTE Officer account request submitted successfully. It is now pending administrative verification."
    }), 201


@api.get("/account-requests")
@authenticated
def list_account_requests():
    if g.user.role != "admin":
        abort(403, description="Only administrators may review account requests.")
    query = select(AccountRequest)
    status_filter = request.args.get("status")
    if status_filter:
        query = query.where(AccountRequest.status == status_filter)
    req_type = request.args.get("type")
    if req_type:
        query = query.where(AccountRequest.request_type == req_type)
    requests = db.session.scalars(query.order_by(AccountRequest.created_at.desc())).all()
    return {"items": [account_request_json(r) for r in requests], "total": len(requests)}


@api.get("/account-requests/<int:req_id>")
@authenticated
def get_account_request(req_id):
    if g.user.role != "admin":
        abort(403, description="Only administrators may review account requests.")
    req = db.session.get(AccountRequest, req_id)
    if not req:
        abort(404, description="Account request not found.")
    return account_request_json(req)


@api.post("/account-requests/<int:req_id>/review")
@authenticated
def review_account_request(req_id):
    if g.user.role != "admin":
        abort(403, description="Only administrators may review account requests.")
    req = db.session.get(AccountRequest, req_id)
    if not req:
        abort(404, description="Account request not found.")
    if req.email == g.user.email:
        abort(403, description="Administrators cannot review their own account request.")
    if req.status != "pending":
        abort(409, description=f"This request has already been reviewed (status: {req.status}).")

    data = parse(AccountRequestReview)
    req.status = data.decision
    req.reviewed_at = now()
    req.reviewer_id = g.user.id
    req.reviewer_decision_reason = data.reason.strip() if data.reason else None

    if data.decision == "approved":
        existing_user = db.session.scalar(select(User).where(User.email == req.email))
        if existing_user:
            abort(409, description="A user with this email address already exists.")

        role = req.request_type
        bureau_id = None
        if req.request_type == "officer":
            bureau = db.session.scalar(select(Bureau).where(Bureau.code == (req.bureau_code or "RB").upper()))
            if not bureau:
                bureau = db.session.scalar(select(Bureau))
            bureau_id = bureau.id if bureau else None

        new_user = User(
            name=req.name,
            email=req.email,
            role=role,
            bureau_id=bureau_id,
            password_hash=req.password_hash,
            active=True
        )
        db.session.add(new_user)
        db.session.flush()
        req.user_id = new_user.id
        event(None, "account_approved", f"Account request approved for {req.email} ({role})", data.reason or "Administrative approval", actor=g.user)
    else:
        event(None, "account_rejected", f"Account request rejected for {req.email} ({req.request_type})", data.reason or "Administrative rejection", actor=g.user)

    db.session.commit()
    return account_request_json(req)


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
    if g.user.role not in ("officer", "lead"):
        abort(403, description="Only officers may register complaints.")
    data = parse(Registration)
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
    if g.user.role == "officer" and owner.id != g.user.id:
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
    event(case, "registered", "Complaint registered", data.deadline_reason)
    enqueue(case)
    db.session.commit()
    return case_json(case, True), 201


@api.get("/complaints/<int:case_id>")
@authenticated
def detail(case_id):
    case = case_or_404(case_id)
    result = case_json(case, True)
    result["attachments"] = [{"id": a.id, "filename": a.filename, "size": a.size, "checksum": a.checksum} for a in db.session.scalars(select(Attachment).where(Attachment.complaint_id == case.id))]
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
    case = case_or_404(case_id, write=True)
    data = parse(StatusChange)
    check_version(case, data.version)
    if data.status not in TRANSITIONS[case.status]:
        abort(422, description="This status transition is not permitted.")
    previous = case.status
    case.status = data.status
    event(case, "reopened" if previous == "disposed" else "status_changed", f"Status changed to {case.status.replace('_', ' ')}",
          data.reason, {"status": {"before": previous, "after": case.status}})
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
    case = case_or_404(case_id, write=True)
    try:
        check_version(case, int(request.form.get("version", "0")))
    except ValueError:
        abort(422, description="Invalid case version.")
    item = request.files.get("file")
    if not item:
        abort(422, description="Choose a PDF, PNG or JPEG file.")
    content = item.read()
    if not content or len(content) > 8 * 1024 * 1024:
        abort(422, description="Evidence must be between 1 byte and 8 MB.")
    media = "application/pdf" if content.startswith(b"%PDF-") else "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if content.startswith(b"\xff\xd8\xff") else None
    name = secure_filename(item.filename or "evidence")[:180]
    ext = Path(name).suffix.lower()
    if not media or ext not in {"application/pdf": [".pdf"], "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]}[media]:
        abort(422, description="File signature and extension must match PDF, PNG or JPEG.")
    key = uuid4().hex
    path = Path(current_app.config["STORAGE_PATH"]) / key
    path.write_bytes(content)
    try:
        db.session.add(Attachment(complaint_id=case.id, filename=name, key=key, media_type=media, size=len(content), checksum=hashlib.sha256(content).hexdigest()))
        event(case, "evidence_added", f"Evidence added: {name}")
        case.version += 1
        db.session.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"ok": True}, 201


@api.get("/attachments/<int:attachment_id>/download")
@authenticated
def download(attachment_id):
    attachment = db.session.get(Attachment, attachment_id)
    if not attachment:
        abort(404)
    case_or_404(attachment.complaint_id)
    path = Path(current_app.config["STORAGE_PATH"]) / attachment.key
    if not path.is_file():
        abort(404, description="Evidence file unavailable.")
    return send_file(path, as_attachment=True, download_name=attachment.filename, mimetype=attachment.media_type)


def authorized_pairs():
    ids = select(Complaint.id).where(scope())
    return select(Pair).where(Pair.case_a_id.in_(ids), Pair.case_b_id.in_(ids))


def pair_json(pair, detailed=False):
    result = {"id": pair.id, "a": case_json(pair.a, detailed), "b": case_json(pair.b, detailed),
              "state": pair.state, "band": pair.band, "evidence": pair.evidence, "version": pair.version}
    result["stale"] = pair.evidence.get("revisions") != {str(pair.a.id): pair.a.content_revision, str(pair.b.id): pair.b.content_revision}
    if detailed:
        result["can_review"] = g.user.role == "reviewer"
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
    if g.user.role != "reviewer":
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
    query = select(ActionEvent).where(ActionEvent.complaint_id.in_(visible))
    if request.args.get("kind"):
        query = query.where(ActionEvent.kind.in_(request.args["kind"].split(",")))
    if request.args.get("actor"):
        query = query.where(ActionEvent.actor_name.ilike("%" + request.args["actor"][:120] + "%"))
    return page(query.order_by(ActionEvent.id.desc()), event_json, ActionEvent)


def attention_key(case):
    priority = {"urgent": 3, "high": 2, "normal": 1, "low": 0}
    urgency = {"overdue": 3, "due_soon": 2, "on_track": 1, "not_set": 0}
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
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reference", "Institution", "Category", "Status", "Bureau", "Owner", "Received UTC", "Due UTC", "Deadline condition"])
    def safe(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for case in db.session.scalars(filtered_cases().order_by(Complaint.id)):
        writer.writerow([safe(v) for v in [case.reference, case.institution.name, case.category, case.status, case.bureau.code, case.owner.name, iso(case.received_at), iso(case.due_at), condition(case)]])
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="onecase-complaints.csv"'
    return response
