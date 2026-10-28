from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint, MetaData, ForeignKeyConstraint
from uuid import uuid4

db = SQLAlchemy(metadata=MetaData(naming_convention={"ix": "ix_%(column_0_label)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}))


def now():
    return datetime.now(timezone.utc)


def iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


class Bureau(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)


class User(db.Model):
    __table_args__ = (db.Index("uq_single_system_administrator", "role", unique=True,
                              postgresql_where=db.text("role = 'admin'"),
                              sqlite_where=db.text("role = 'admin'")),)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(30), nullable=False, default="officer")
    requested_role = db.Column(db.String(30))
    organization = db.Column(db.String(200))
    bureau_id = db.Column(db.Integer, db.ForeignKey("bureau.id"))
    active = db.Column(db.Boolean, nullable=False, default=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    mfa_secret = db.Column(db.Text)
    mfa_pending_secret = db.Column(db.Text)
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    recovery_codes = db.Column(db.JSON, nullable=False, default=list, server_default="[]")
    last_totp_step = db.Column(db.BigInteger)
    bureau = db.relationship(Bureau)


class Session(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    csrf = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, server_default=db.func.now())
    authenticated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, server_default=db.func.now())
    user = db.relationship(User)


class PasswordReset(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))


class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False, index=True)
    at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class Institution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    external_id = db.Column(db.String(60), unique=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    region = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(300), nullable=False)


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(40), nullable=False, unique=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    issue_summary = db.Column(db.String(300), nullable=False, default="", server_default='')
    complainant_type = db.Column(db.String(40), nullable=False, default="student", server_default='student')
    affected_person = db.Column(db.String(150), nullable=False, default="", server_default='')
    submitter_name = db.Column(db.String(150), nullable=False, default="", server_default='')
    representation_basis = db.Column(db.String(1000), nullable=False, default="", server_default='')
    source_channel = db.Column(db.String(60), nullable=False, default="Officer recording", server_default='Officer recording')
    source_reference = db.Column(db.String(150), nullable=False, default="", server_default='')
    entered_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, server_default=db.func.now())
    prior_proceedings = db.Column(db.Text, nullable=False, default="", server_default='')
    sensitivity = db.Column(db.String(30), nullable=False, default="standard", server_default='standard')
    taxonomy_version = db.Column(db.String(40), nullable=False, default="onecase-demo-v2", server_default='onecase-demo-v2')
    priority = db.Column(db.String(20), nullable=False, default="normal")
    status = db.Column(db.String(30), nullable=False, default="received", index=True)
    bureau_id = db.Column(db.Integer, db.ForeignKey("bureau.id"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    submitter_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, index=True)
    due_at = db.Column(db.DateTime(timezone=True), index=True)
    deadline_policy = db.Column(db.String(120), nullable=False, default="Illustrative elapsed-time policy v1")
    deadline_revision = db.Column(db.Integer, nullable=False, default=1)
    deadline_config = db.Column(db.JSON, nullable=False, default=dict)
    paused_at = db.Column(db.DateTime(timezone=True))
    next_action = db.Column(db.String(500), nullable=False, default="Review the complaint")
    version = db.Column(db.Integer, nullable=False, default=1)
    content_revision = db.Column(db.Integer, nullable=False, default=1)
    matching_state = db.Column(db.String(30), nullable=False, default="queued")
    matching_error = db.Column(db.String(300))
    institution = db.relationship(Institution)
    bureau = db.relationship(Bureau)
    owner = db.relationship(User, foreign_keys=[owner_id])
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        UniqueConstraint("id", "institution_id", name="uq_complaint_id_institution"),
        CheckConstraint("status IN ('received','under_review','awaiting_information','disposed')"),
        CheckConstraint("priority IN ('low','normal','high','urgent')"),
    )


class CaseWorkflow(db.Model):
    """Case-bound internal handling, separate from external legal proceedings."""
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), primary_key=True)
    stage = db.Column(db.String(30), nullable=False, default="initial_review")
    cycle = db.Column(db.Integer, nullable=False, default=1)
    version = db.Column(db.Integer, nullable=False, default=1)
    faculty_reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    officer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    lead_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    committee_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    verifier_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    auditor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    executive_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    access_until = db.Column(db.DateTime(timezone=True), nullable=False)
    auditor_required = db.Column(db.Boolean, nullable=False, default=False)
    outcome = db.Column(db.String(30))
    public_decision = db.Column(db.Text, nullable=False, default="")
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (CheckConstraint("stage IN ('initial_review','officer_triage','committee_review','investigation','executive_decision','resolved','appeal_review')"),)


class CaseWorkflowReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("case_workflow.complaint_id"), nullable=False, index=True)
    cycle = db.Column(db.Integer, nullable=False)
    stage = db.Column(db.String(30), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    report = db.Column(db.Text, nullable=False)
    evidence_ids = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class Grant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now, server_default=db.func.now())
    expires_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    fields = db.Column(db.JSON, nullable=False, default=lambda: ["basic", "content"], server_default='["basic", "content"]')
    reason = db.Column(db.String(1000), nullable=False, default="Explicit case read access", server_default="Legacy explicit case read access")
    __table_args__ = (UniqueConstraint("user_id", "complaint_id"),)


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False, index=True)
    bureau_id = db.Column(db.Integer, db.ForeignKey("bureau.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    ended_at = db.Column(db.DateTime(timezone=True))
    reason = db.Column(db.String(2000), nullable=False)


class Transfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    from_owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    to_owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    acknowledged_at = db.Column(db.DateTime(timezone=True))


class ActionEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    actor_name = db.Column(db.String(120), nullable=False)
    bureau_id = db.Column(db.Integer, db.ForeignKey("bureau.id"))
    kind = db.Column(db.String(60), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    reason = db.Column(db.Text, nullable=False, default="")
    changes = db.Column(db.JSON, nullable=False, default=dict)
    outcome = db.Column(db.String(20), nullable=False, default="succeeded")
    severity = db.Column(db.String(20), nullable=False, default="info")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, index=True)
    request_id = db.Column(db.String(64), nullable=False, default="", server_default="")
    complaint = db.relationship(Complaint)


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    upload_key = db.Column(db.String(100))
    filename = db.Column(db.String(200), nullable=False)
    key = db.Column(db.String(80), nullable=False, unique=True)
    storage_backend = db.Column(db.String(20), nullable=False, default="local", server_default="local")
    storage_bucket = db.Column(db.String(100))
    media_type = db.Column(db.String(80), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    checksum = db.Column(db.String(64), nullable=False)
    proceeding_id = db.Column(db.Integer, db.ForeignKey("proceeding.id"))
    sensitivity = db.Column(db.String(30), nullable=False, default="standard", server_default='standard')
    scan_state = db.Column(db.String(30), nullable=False, default="pending", server_default="pending")
    scan_checked_at = db.Column(db.DateTime(timezone=True))
    scan_detail = db.Column(db.String(300))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (UniqueConstraint("id", "complaint_id", name="uq_attachment_id_complaint"),
                     UniqueConstraint("complaint_id", "upload_key", name="uq_attachment_complaint_upload_key"))


class ComplaintReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False, index=True)
    closure_event_id = db.Column(db.Integer, db.ForeignKey("action_event.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    pdf = db.Column(db.LargeBinary, nullable=False)
    checksum = db.Column(db.String(64), nullable=False)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"))
    kind = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    dedup_key = db.Column(db.String(180), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    read_at = db.Column(db.DateTime(timezone=True))


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    dedup_key = db.Column(db.String(150), nullable=False, unique=True)
    state = db.Column(db.String(20), nullable=False, default="queued", index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    available_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    lease_until = db.Column(db.DateTime(timezone=True))
    error = db.Column(db.String(300))


class WorkerHeartbeat(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    seen_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    succeeded_at = db.Column(db.DateTime(timezone=True))
    failed_stages = db.Column(db.JSON, nullable=False, default=list)


class MatchingRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    bundle = db.Column(db.JSON, nullable=False)
    evidence = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class Embedding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    issue_id = db.Column(db.String(36), db.ForeignKey("complaint_issue.id"))
    revision = db.Column(db.Integer, nullable=False)
    model = db.Column(db.String(250), nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    vector = db.Column(db.JSON, nullable=False)
    truncated = db.Column(db.Boolean, nullable=False)
    __table_args__ = (UniqueConstraint("complaint_id", "revision", "model"),)


class Pair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_a_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    case_b_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey("matching_run.id"), nullable=False)
    evidence = db.Column(db.JSON, nullable=False)
    band = db.Column(db.String(20), nullable=False)
    state = db.Column(db.String(20), nullable=False, default="pending")
    version = db.Column(db.Integer, nullable=False, default=1)
    a = db.relationship(Complaint, foreign_keys=[case_a_id])
    b = db.relationship(Complaint, foreign_keys=[case_b_id])
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (UniqueConstraint("case_a_id", "case_b_id"), CheckConstraint("case_a_id < case_b_id"))


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair_id = db.Column(db.Integer, db.ForeignKey("pair.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    decision = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    revisions = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    user = db.relationship(User)


class Idempotency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "key"),)


class SLAPause(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ended_at = db.Column(db.DateTime(timezone=True))
    reason = db.Column(db.String(2000), nullable=False)


class PairScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pair_id = db.Column(db.Integer, db.ForeignKey("pair.id"), nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey("matching_run.id"), nullable=False)
    evidence = db.Column(db.JSON, nullable=False)
    __table_args__ = (UniqueConstraint("pair_id", "run_id"),)


class RoleAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    role = db.Column(db.String(40), nullable=False)
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now, server_default=db.func.now())
    expires_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    approval_reference = db.Column(db.String(200), nullable=False)
    reason = db.Column(db.String(1000), nullable=False)


class PermissionGrant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    operation = db.Column(db.String(60), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"))
    bureau_id = db.Column(db.Integer, db.ForeignKey("bureau.id"))
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"))
    region = db.Column(db.String(80))
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now, server_default=db.func.now())
    expires_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    approval_reference = db.Column(db.String(200), nullable=False)
    reason = db.Column(db.String(1000), nullable=False)


class Proceeding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False)
    external_authority = db.Column(db.String(200), nullable=False)
    institution_type = db.Column(db.String(60), nullable=False)
    jurisdiction = db.Column(db.String(100), nullable=False)
    framework = db.Column(db.String(200), nullable=False)
    framework_version = db.Column(db.String(80), nullable=False)
    applicability_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    authority_reference = db.Column(db.String(200), nullable=False)
    destination_validated = db.Column(db.Boolean, nullable=False, default=False)
    stage = db.Column(db.String(50), nullable=False, default="screening")
    state = db.Column(db.String(30), nullable=False, default="active")
    context = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    proceeding_id = db.Column(db.Integer, db.ForeignKey("proceeding.id"), nullable=False)
    designation = db.Column(db.String(150), nullable=False)
    capacity = db.Column(db.String(30), nullable=False)
    permissions = db.Column(db.JSON, nullable=False, default=list)
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now, server_default=db.func.now())
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    recused_at = db.Column(db.DateTime(timezone=True))
    approval_reference = db.Column(db.String(200), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class CaseConflict(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    decision_reference = db.Column(db.String(200), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    resolved_at = db.Column(db.DateTime(timezone=True))


class ProceedingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proceeding_id = db.Column(db.Integer, db.ForeignKey("proceeding.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    details = db.Column(db.JSON, nullable=False)
    attachment_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))
    original_record_id = db.Column(db.Integer, db.ForeignKey("proceeding_record.id"))
    issuer = db.Column(db.String(200), nullable=False, default="")
    verification_reference = db.Column(db.String(300), nullable=False, default="")
    finalized = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class MilestonePolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    version = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(500), nullable=False)
    clause = db.Column(db.String(200), nullable=False)
    route = db.Column(db.String(40), nullable=False)
    institution_type = db.Column(db.String(60), nullable=False)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    administrative = db.Column(db.Boolean, nullable=False, default=True)
    mode = db.Column(db.String(20), nullable=False)
    minutes = db.Column(db.Integer, nullable=False)
    calendar = db.Column(db.JSON, nullable=False, default=dict)
    start_event = db.Column(db.String(100), nullable=False)
    pause_rule = db.Column(db.String(300), nullable=False)
    effective_from = db.Column(db.DateTime(timezone=True), nullable=False)
    effective_until = db.Column(db.DateTime(timezone=True))
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    approval_reference = db.Column(db.String(200), nullable=False)
    __table_args__ = (UniqueConstraint("name", "version"),)


class Milestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proceeding_id = db.Column(db.Integer, db.ForeignKey("proceeding.id"), nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    policy_snapshot = db.Column(db.JSON, nullable=False)
    start_at = db.Column(db.DateTime(timezone=True), nullable=False)
    original_due_at = db.Column(db.DateTime(timezone=True))
    due_at = db.Column(db.DateTime(timezone=True))
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    state = db.Column(db.String(30), nullable=False, default="pending")
    completed_at = db.Column(db.DateTime(timezone=True))
    revision = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}


class ComplianceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proceeding_id = db.Column(db.Integer, db.ForeignKey("proceeding.id"), nullable=False, index=True)
    direction_record_id = db.Column(db.Integer, db.ForeignKey("proceeding_record.id"), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    responsible_party = db.Column(db.String(200), nullable=False)
    respondent_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    verifier_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    state = db.Column(db.String(30), nullable=False, default="pending")
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}


class ComplianceSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("compliance_item.id"), nullable=False)
    attachment_id = db.Column(db.Integer, db.ForeignKey("attachment.id"), nullable=False)
    submitted_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    submitting_party = db.Column(db.String(200), nullable=False)
    note = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class ComplianceVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("compliance_item.id"), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey("compliance_submission.id"), nullable=False)
    verifier_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    outcome = db.Column(db.String(30), nullable=False)
    observations = db.Column(db.Text, nullable=False)
    reason = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class DispatchPacket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proceeding_id = db.Column(db.Integer, db.ForeignKey("proceeding.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    manifest = db.Column(db.JSON, nullable=False)
    state = db.Column(db.String(30), nullable=False, default="prepared")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    dispatched_at = db.Column(db.DateTime(timezone=True))
    dispatch_channel = db.Column(db.String(100))
    dispatch_reference = db.Column(db.String(200))
    delivery_attachment_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))
    acknowledged_at = db.Column(db.DateTime(timezone=True))
    acknowledgement_reference = db.Column(db.String(200))
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}


def opaque_id():
    return str(uuid4())


class Person(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    display_name = db.Column(db.String(150), nullable=False, index=True)
    record_state = db.Column(db.String(30), nullable=False, default="provisional")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, onupdate=now)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}


class Location(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    country = db.Column(db.String(80), nullable=False, default="")
    state = db.Column(db.String(80), nullable=False, default="")
    district = db.Column(db.String(100), nullable=False, default="")
    city = db.Column(db.String(100), nullable=False, default="")
    locality = db.Column(db.String(150), nullable=False, default="")
    postal_information = db.Column(db.String(100), nullable=False, default="")
    code_system = db.Column(db.String(80))
    official_code = db.Column(db.String(80))
    geographic_level = db.Column(db.String(40))
    source = db.Column(db.String(300), nullable=False)
    verification_state = db.Column(db.String(30), nullable=False, default="self_declared")
    __table_args__ = (UniqueConstraint("code_system", "geographic_level", "official_code", name="uq_location_scoped_official_code"),)


class Campus(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    location_id = db.Column(db.String(36), db.ForeignKey("location.id"))
    verification_state = db.Column(db.String(30), nullable=False, default="unverified")
    source = db.Column(db.String(300), nullable=False)
    __table_args__ = (UniqueConstraint("id", "institution_id", name="uq_campus_id_institution"),)


class IdentityIssuer(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    name = db.Column(db.String(200), nullable=False)
    namespace = db.Column(db.String(100), nullable=False, unique=True)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"))
    source = db.Column(db.String(300), nullable=False)


class PersonContact(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    person_id = db.Column(db.String(36), db.ForeignKey("person.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False)
    value_ciphertext = db.Column(db.Text, nullable=False)
    purpose = db.Column(db.String(200), nullable=False)
    source = db.Column(db.String(300), nullable=False)
    state = db.Column(db.String(30), nullable=False, default="pending")
    method = db.Column(db.String(100))
    checked_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))


class IdentityClaim(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    person_id = db.Column(db.String(36), db.ForeignKey("person.id"), nullable=False, index=True)
    issuer_id = db.Column(db.String(36), db.ForeignKey("identity_issuer.id"), nullable=False)
    namespace = db.Column(db.String(100), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    identifier_ciphertext = db.Column(db.Text, nullable=False)
    identifier_digest = db.Column(db.String(64), nullable=False, index=True)
    source = db.Column(db.String(300), nullable=False)
    attachment_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))
    valid_from = db.Column(db.DateTime(timezone=True))
    valid_until = db.Column(db.DateTime(timezone=True))
    state = db.Column(db.String(30), nullable=False, default="needs_review")
    __table_args__ = (CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_identity_claim_valid_range"),)


class IdentityVerification(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    person_id = db.Column(db.String(36), db.ForeignKey("person.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    claim_id = db.Column(db.String(36), db.ForeignKey("identity_claim.id"))
    contact_id = db.Column(db.String(36), db.ForeignKey("person_contact.id"))
    check_type = db.Column(db.String(60), nullable=False)
    method = db.Column(db.String(100), nullable=False)
    outcome = db.Column(db.String(30), nullable=False)
    evidence_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))
    reference = db.Column(db.String(300), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    expires_at = db.Column(db.DateTime(timezone=True))
    reason = db.Column(db.String(2000), nullable=False)
    supersedes_id = db.Column(db.String(36), db.ForeignKey("identity_verification.id"))


class PersonLocation(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    person_id = db.Column(db.String(36), db.ForeignKey("person.id"), nullable=False)
    location_id = db.Column(db.String(36), db.ForeignKey("location.id"), nullable=False)
    relationship = db.Column(db.String(40), nullable=False)
    effective_from = db.Column(db.DateTime(timezone=True), nullable=False)
    effective_until = db.Column(db.DateTime(timezone=True))
    source = db.Column(db.String(300), nullable=False)
    checked = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint("effective_until IS NULL OR effective_until >= effective_from", name="ck_person_location_valid_range"),)


class ComplaintParticipant(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False, index=True)
    person_id = db.Column(db.String(36), db.ForeignKey("person.id"), nullable=False)
    role = db.Column(db.String(40), nullable=False)
    source = db.Column(db.String(300), nullable=False)
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    expires_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("complaint_id", "person_id", "role", name="uq_complaint_person_role"),)


class RepresentativeAuthorization(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    representative_id = db.Column(db.String(36), db.ForeignKey("person.id"), nullable=False)
    represented_person_id = db.Column(db.String(36), db.ForeignKey("person.id"), nullable=False)
    basis = db.Column(db.String(1000), nullable=False)
    evidence_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    expires_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    disclosure_scope = db.Column(db.String(500), nullable=False)
    __table_args__ = (CheckConstraint("representative_id <> represented_person_id", name="ck_representative_distinct_person"),)


class ComplaintSource(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False, index=True)
    namespace = db.Column(db.String(100), nullable=False)
    reference = db.Column(db.String(150), nullable=False)
    original_received_at = db.Column(db.DateTime(timezone=True), nullable=False)
    imported_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    payload_digest = db.Column(db.String(64), nullable=False)
    provenance = db.Column(db.String(500), nullable=False)
    guaranteed_record_key = db.Column(db.String(64), unique=True)


class ComplaintIssue(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    complaint_id = db.Column(db.Integer, nullable=False, index=True)
    institution_id = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    subcategory = db.Column(db.String(100), nullable=False, default="")
    summary = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    campus_id = db.Column(db.String(36))
    incident_location_id = db.Column(db.String(36), db.ForeignKey("location.id"))
    incident_start = db.Column(db.DateTime(timezone=True))
    incident_end = db.Column(db.DateTime(timezone=True))
    incident_precision = db.Column(db.String(20), nullable=False, default="unknown")
    requested_relief = db.Column(db.String(2000), nullable=False, default="")
    state = db.Column(db.String(30), nullable=False, default="open")
    revision = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(300), nullable=False)
    __mapper_args__ = {"version_id_col": revision}
    __table_args__ = (
        UniqueConstraint("id", "complaint_id", name="uq_issue_id_complaint"),
        ForeignKeyConstraint(["complaint_id", "institution_id"], ["complaint.id", "complaint.institution_id"], name="fk_issue_case_institution"),
        ForeignKeyConstraint(["campus_id", "institution_id"], ["campus.id", "campus.institution_id"], name="fk_issue_campus_institution"),
        CheckConstraint("incident_end IS NULL OR incident_start IS NULL OR incident_end >= incident_start", name="ck_issue_incident_range"),
        CheckConstraint("incident_precision IN ('unknown','day','month','year','range')", name="ck_issue_incident_precision"),
    )


class IssueEvidence(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    issue_id = db.Column(db.String(36), nullable=False)
    complaint_id = db.Column(db.Integer, nullable=False)
    attachment_id = db.Column(db.Integer, nullable=False)
    relevance_note = db.Column(db.String(1000), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (
        ForeignKeyConstraint(["issue_id", "complaint_id"], ["complaint_issue.id", "complaint_issue.complaint_id"], name="fk_issue_evidence_case"),
        ForeignKeyConstraint(["attachment_id", "complaint_id"], ["attachment.id", "attachment.complaint_id"], name="fk_issue_evidence_attachment_case"),
        UniqueConstraint("issue_id", "attachment_id", name="uq_issue_evidence"),
    )


class IncidentRecord(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    institution_id = db.Column(db.Integer, db.ForeignKey("institution.id"), nullable=False)
    summary = db.Column(db.String(300), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    basis = db.Column(db.String(2000), nullable=False)
    uncertainty = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class IssueIncidentLink(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    issue_id = db.Column(db.String(36), db.ForeignKey("complaint_issue.id"), nullable=False)
    incident_id = db.Column(db.String(36), db.ForeignKey("incident_record.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    basis = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    revoked_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("issue_id", "incident_id", name="uq_issue_incident"),)


class IssuePairFinding(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    pair_id = db.Column(db.Integer, db.ForeignKey("pair.id"), nullable=False, index=True)
    issue_a_id = db.Column(db.String(36), db.ForeignKey("complaint_issue.id"), nullable=False)
    issue_b_id = db.Column(db.String(36), db.ForeignKey("complaint_issue.id"), nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey("matching_run.id"), nullable=False)
    evidence = db.Column(db.JSON, nullable=False)
    state = db.Column(db.String(30), nullable=False, default="pending")
    relation_kind = db.Column(db.String(40))
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (UniqueConstraint("pair_id", "issue_a_id", "issue_b_id", name="uq_case_issue_pair"), CheckConstraint("issue_a_id <> issue_b_id", name="ck_distinct_issue_pair"))


class IssueReview(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=opaque_id)
    finding_id = db.Column(db.String(36), db.ForeignKey("issue_pair_finding.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    decision = db.Column(db.String(30), nullable=False)
    relation_kind = db.Column(db.String(40))
    reason = db.Column(db.String(2000), nullable=False)
    revisions = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
