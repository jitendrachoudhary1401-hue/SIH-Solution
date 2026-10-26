from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()


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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(30), nullable=False, default="officer")
    bureau_id = db.Column(db.Integer, db.ForeignKey("bureau.id"))
    active = db.Column(db.Boolean, nullable=False, default=True)
    bureau = db.relationship(Bureau)


class Session(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    csrf = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    user = db.relationship(User)


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
    issue_summary = db.Column(db.String(300), nullable=False, default="")
    complainant_type = db.Column(db.String(40), nullable=False, default="student")
    affected_person = db.Column(db.String(150), nullable=False, default="")
    submitter_name = db.Column(db.String(150), nullable=False, default="")
    representation_basis = db.Column(db.String(1000), nullable=False, default="")
    source_channel = db.Column(db.String(60), nullable=False, default="Officer recording")
    source_reference = db.Column(db.String(150), nullable=False, default="")
    entered_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    prior_proceedings = db.Column(db.Text, nullable=False, default="")
    sensitivity = db.Column(db.String(30), nullable=False, default="standard")
    taxonomy_version = db.Column(db.String(40), nullable=False, default="onecase-demo-v2")
    priority = db.Column(db.String(20), nullable=False, default="normal")
    status = db.Column(db.String(30), nullable=False, default="received", index=True)
    bureau_id = db.Column(db.Integer, db.ForeignKey("bureau.id"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
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
    owner = db.relationship(User)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        CheckConstraint("status IN ('received','under_review','awaiting_information','disposed')"),
        CheckConstraint("priority IN ('low','normal','high','urgent')"),
    )


class Grant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    expires_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    fields = db.Column(db.JSON, nullable=False, default=lambda: ["basic", "content"])
    reason = db.Column(db.String(1000), nullable=False, default="Explicit case read access")
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
    complaint = db.relationship(Complaint)


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    key = db.Column(db.String(80), nullable=False, unique=True)
    media_type = db.Column(db.String(80), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    checksum = db.Column(db.String(64), nullable=False)
    proceeding_id = db.Column(db.Integer, db.ForeignKey("proceeding.id"))
    sensitivity = db.Column(db.String(30), nullable=False, default="standard")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


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
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
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
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
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
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
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
