"""Case-bound proceedings, distinct milestone clocks, independent verification and dispatch."""
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, abort, current_app, g, request, send_file
from pydantic import Field, field_validator
from sqlalchemy import select
from .models import (db, now, iso, User, Complaint, Attachment, Proceeding, ProceedingRecord, Appointment,
                     CaseConflict, MilestonePolicy, Milestone, ComplianceItem, ComplianceSubmission,
                     ComplianceVerification, DispatchPacket)
from .auth import (authenticated, case_or_404, allowed, roles, proceeding_allowed, document_allowed,
                   check_version, scope)
from .api import Input, Change, parse, event, notify

workflow_api = Blueprint("workflow", __name__)
ROUTES = {"student_institution", "faculty_staff", "appeal", "regulatory_referral", "manual_review"}
RECORD_KINDS = {"records_request", "response", "notice", "meeting", "observation", "recommendation", "decision", "report", "service", "addendum", "conflict", "recusal"}
MILESTONES = {"report_due", "notice_service", "information_response", "compliance_due", "appeal_filing", "monitoring_target"}


class ProceedingInput(Change):
    kind: str
    external_authority: str = Field(min_length=3, max_length=200)
    authority_reference: str = Field(min_length=3, max_length=200)
    institution_type: str = Field(min_length=2, max_length=60)
    jurisdiction: str = Field(min_length=2, max_length=100)
    framework: str = Field(min_length=3, max_length=200)
    framework_version: str = Field(min_length=1, max_length=80)
    applicability_confirmed: bool = False
    destination_validated: bool = False
    source_reference: str = Field(default="", max_length=500)
    challenged_record_id: int | None = None
    grounds: str = Field(default="", max_length=2000)
    requested_relief: str = Field(default="", max_length=2000)
    service_date: datetime | None = None
    appeal_policy: str = Field(default="", max_length=300)


class RecordInput(Change):
    kind: str
    title: str = Field(min_length=3, max_length=200)
    allegations: str = Field(default="", max_length=4000)
    evidence: str = Field(default="", max_length=4000)
    findings: str = Field(default="", max_length=4000)
    recommendations: str = Field(default="", max_length=4000)
    directions: str = Field(default="", max_length=4000)
    recipients: str = Field(default="", max_length=1000)
    scheduled_at: datetime | None = None
    delivery_reference: str = Field(default="", max_length=300)
    attachment_id: int | None = None
    original_record_id: int | None = None
    issuer: str = Field(default="", max_length=200)
    verification_reference: str = Field(default="", max_length=300)
    finalized: bool = False
    external_document: bool = False


class MilestoneInput(Change):
    kind: str
    title: str = Field(min_length=3, max_length=200)
    start_at: datetime
    due_at: datetime | None = None
    policy_id: int | None = None
    recipient_id: int
    @field_validator("start_at", "due_at")
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("Timezone-aware timestamps required")
        return value


class MilestoneChange(Change):
    due_at: datetime | None = None
    completed: bool = False


class ComplianceInput(Change):
    direction_record_id: int
    title: str = Field(min_length=3, max_length=300)
    responsible_party: str = Field(min_length=3, max_length=200)
    verifier_id: int
    respondent_user_id: int | None = None


class SubmissionInput(Change):
    attachment_id: int
    submitting_party: str = Field(min_length=3, max_length=200)


class VerificationInput(Change):
    submission_id: int
    outcome: str
    observations: str = Field(min_length=10, max_length=5000)


class PacketInput(Change):
    attachment_ids: list[int] = Field(min_length=1, max_length=20)


class DispatchInput(Change):
    channel: str = Field(min_length=2, max_length=100)
    reference: str = Field(min_length=3, max_length=200)
    occurred_at: datetime
    delivery_attachment_id: int


class AcknowledgeInput(Change):
    reference: str = Field(min_length=3, max_length=200)
    occurred_at: datetime


def proceeding_or_404(proceeding_id, operation="read"):
    item = db.session.get(Proceeding, proceeding_id)
    if not item or not proceeding_allowed(item, operation):
        abort(404, description="Proceeding unavailable for this appointment or permission.")
    return item, case_or_404(item.complaint_id)


def evidence_or_422(case, attachment_id, proceeding=None, clean=True):
    item = db.session.get(Attachment, attachment_id) if attachment_id else None
    if not item or item.complaint_id != case.id or not document_allowed(case, item):
        abort(422, description="Select evidence available within your document scope.")
    if proceeding and item.proceeding_id not in (None, proceeding.id):
        abort(422, description="Evidence belongs to another proceeding.")
    from .documents import evidence_available
    if clean and not evidence_available(item):
        abort(422, description="Evidence must pass validation and malware scanning before use or download.")
    return item


def milestone_condition(item):
    if item.completed_at:
        return "completed"
    snapshot = item.policy_snapshot
    if not snapshot.get("confirmed") and not snapshot.get("administrative"):
        return "policy_confirmation_required"
    if not item.due_at:
        return "policy_confirmation_required"
    from datetime import timedelta
    due = item.due_at.replace(tzinfo=timezone.utc)
    return "overdue" if due < now() else "due_soon" if due < now() + timedelta(days=2) else "on_track"


def proceeding_json(item, case):
    can_coordinate = proceeding_allowed(item, "coordinate")
    records = db.session.scalars(select(ProceedingRecord).where(ProceedingRecord.proceeding_id == item.id).order_by(ProceedingRecord.id)).all()
    milestones = db.session.scalars(select(Milestone).where(Milestone.proceeding_id == item.id).order_by(Milestone.id)).all()
    compliance = db.session.scalars(select(ComplianceItem).where(ComplianceItem.proceeding_id == item.id).order_by(ComplianceItem.id)).all()
    packets = db.session.scalars(select(DispatchPacket).where(DispatchPacket.proceeding_id == item.id).order_by(DispatchPacket.id.desc())).all()
    return {"id": item.id, "kind": item.kind, "external_authority": item.external_authority, "authority_reference": item.authority_reference,
            "institution_type": item.institution_type, "jurisdiction": item.jurisdiction, "framework": item.framework,
            "framework_version": item.framework_version, "applicability_confirmed": item.applicability_confirmed,
            "destination_validated": item.destination_validated, "stage": item.stage, "state": item.state, "version": item.version,
            "context": item.context, "created_at": iso(item.created_at),
            "permissions": {"coordinate": can_coordinate, "contribute": proceeding_allowed(item, "contribute"),
                            "finalize": proceeding_allowed(item, "finalize"), "import": proceeding_allowed(item, "import"),
                            "packet": proceeding_allowed(item, "packet"), "compliance": allowed(case, "case.compliance")},
            "records": [{"id": r.id, "kind": r.kind, "title": r.title, "details": r.details,
                         "attachment_id": r.attachment_id if r.attachment_id and document_allowed(case, db.session.get(Attachment, r.attachment_id)) else None,
                         "original_record_id": r.original_record_id, "issuer": r.issuer, "verification_reference": r.verification_reference,
                         "finalized": r.finalized, "created_at": iso(r.created_at)} for r in records],
            "milestones": [{"id": m.id, "kind": m.kind, "title": m.title, "start_at": iso(m.start_at), "due_at": iso(m.due_at),
                            "original_due_at": iso(m.original_due_at), "condition": milestone_condition(m), "policy": m.policy_snapshot,
                            "revision": m.revision, "completed_at": iso(m.completed_at)} for m in milestones],
            "compliance": [compliance_json(c, case) for c in compliance],
            "packets": [{"id": p.id, "state": p.state, "version": p.version, "created_at": iso(p.created_at),
                         "manifest": p.manifest if can_coordinate or proceeding_allowed(item, "packet") else {"note": "Packet metadata restricted"},
                         "dispatched_at": iso(p.dispatched_at), "dispatch_reference": p.dispatch_reference,
                         "acknowledged_at": iso(p.acknowledged_at), "acknowledgement_reference": p.acknowledgement_reference} for p in packets]}


def compliance_json(item, case):
    submissions = db.session.scalars(select(ComplianceSubmission).where(ComplianceSubmission.item_id == item.id).order_by(ComplianceSubmission.id)).all()
    verifications = db.session.scalars(select(ComplianceVerification).where(ComplianceVerification.item_id == item.id).order_by(ComplianceVerification.id)).all()
    can_verify = "verifier" in roles() and item.verifier_id == g.user.id and item.respondent_user_id != g.user.id
    return {"id": item.id, "title": item.title, "responsible_party": item.responsible_party, "state": item.state,
            "version": item.version, "verifier_id": item.verifier_id, "can_submit": allowed(case, "case.compliance"),
            "can_verify": can_verify,
            "submissions": [{"id": s.id, "attachment_id": s.attachment_id if document_allowed(case, db.session.get(Attachment, s.attachment_id)) else None,
                             "submitting_party": s.submitting_party, "note": s.note, "created_at": iso(s.created_at),
                             "can_verify": can_verify and s.submitted_by != g.user.id} for s in submissions],
            "verifications": [{"id": v.id, "outcome": v.outcome, "observations": v.observations, "reason": v.reason,
                               "verifier_id": v.verifier_id, "created_at": iso(v.created_at)} for v in verifications]}


@workflow_api.get("/complaints/<int:case_id>/workflow")
@authenticated
def case_workflow(case_id):
    case = case_or_404(case_id)
    proceedings = db.session.scalars(select(Proceeding).where(Proceeding.complaint_id == case.id).order_by(Proceeding.id)).all()
    return {"items": [proceeding_json(p, case) for p in proceedings if proceeding_allowed(p)],
            "internal_owner": {"bureau": case.bureau.code, "officer": case.owner.name},
            "can_create": allowed(case, "case.route"), "asOf": iso(now())}


@workflow_api.post("/complaints/<int:case_id>/proceedings")
@authenticated
def create_proceeding(case_id):
    case = case_or_404(case_id, operation="case.route")
    data = parse(ProceedingInput)
    check_version(case, data.version)
    if data.kind not in ROUTES:
        abort(422, description="Select a supported route.")
    if data.kind == "student_institution" and case.complainant_type != "student" or data.kind == "faculty_staff" and case.complainant_type not in ("faculty", "staff"):
        abort(422, description="The route must match the complainant type; use manual review when jurisdiction is unclear.")
    if data.applicability_confirmed and not data.source_reference:
        abort(422, description="Confirmed applicability requires an authoritative source reference.")
    if data.kind == "appeal":
        record = db.session.get(ProceedingRecord, data.challenged_record_id)
        parent = db.session.get(Proceeding, record.proceeding_id) if record else None
        if not record or not parent or parent.complaint_id != case.id or not record.finalized or not proceeding_allowed(parent):
            abort(422, description="An appeal must reference an authorized finalized decision or report.")
        if not all([data.grounds, data.requested_relief, data.service_date, data.appeal_policy, data.destination_validated]):
            abort(422, description="Record grounds, requested relief, service date, appeal policy and a validated destination.")
    context = {key: getattr(data, key) for key in ("source_reference", "challenged_record_id", "grounds", "requested_relief", "appeal_policy")}
    context["service_date"] = iso(data.service_date)
    item = Proceeding(complaint_id=case.id, kind=data.kind, external_authority=data.external_authority,
                      authority_reference=data.authority_reference, institution_type=data.institution_type, jurisdiction=data.jurisdiction,
                      framework=data.framework, framework_version=data.framework_version, applicability_confirmed=data.applicability_confirmed,
                      destination_validated=data.destination_validated, context=context)
    db.session.add(item)
    case.version += 1
    db.session.flush()
    event(case, "route_recorded", f"Route recorded: {data.kind.replace('_', ' ')}", data.reason,
          {"proceeding_id": item.id, "external_authority": data.external_authority, "internal_owner_unchanged": True})
    db.session.commit()
    return proceeding_json(item, case), 201


@workflow_api.post("/proceedings/<int:proceeding_id>/records")
@authenticated
def add_record(proceeding_id):
    item, case = proceeding_or_404(proceeding_id)
    data = parse(RecordInput)
    check_version(item, data.version)
    if data.kind not in RECORD_KINDS:
        abort(422, description="Invalid proceeding record type.")
    if data.finalized:
        operation = "import" if data.external_document else "finalize"
        if not proceeding_allowed(item, operation):
            abort(403, description="Only the appointed finalizer may publish a report; verified external documents retain their issuer.")
        if not data.issuer or not data.verification_reference or not data.attachment_id:
            abort(422, description="Final records require an approved document, issuing authority and verification reference.")
    elif not (proceeding_allowed(item, "coordinate") or proceeding_allowed(item, "contribute")):
        abort(403, description="A current contributing or coordinating appointment is required.")
    if data.kind in ("notice", "records_request", "service") and not proceeding_allowed(item, "coordinate"):
        abort(403, description="This record requires a coordinator grant.")
    if data.kind == "service" and not data.delivery_reference:
        abort(422, description="Service requires an actual delivery/acknowledgement reference.")
    if data.attachment_id:
        evidence_or_422(case, data.attachment_id, item)
    if data.original_record_id:
        original = db.session.get(ProceedingRecord, data.original_record_id)
        if not original or original.proceeding_id != item.id or data.kind != "addendum":
            abort(422, description="Corrections must be addenda referencing a record in this proceeding.")
    details = {key: getattr(data, key) for key in ("allegations", "evidence", "findings", "recommendations", "directions", "recipients", "delivery_reference", "external_document")}
    details["scheduled_at"] = iso(data.scheduled_at)
    record = ProceedingRecord(proceeding_id=item.id, kind=data.kind, title=data.title, details=details,
                              attachment_id=data.attachment_id, original_record_id=data.original_record_id, issuer=data.issuer,
                              verification_reference=data.verification_reference, finalized=data.finalized, created_by=g.user.id)
    db.session.add(record)
    item.stage = {"records_request": "records_requested", "report": "report_issued" if data.finalized else "examination", "decision": "decision_recorded", "service": "decision_served"}.get(data.kind, item.stage)
    item.version += 1
    event(case, "proceeding_recorded", f"Proceeding record: {data.title}", data.reason, {"proceeding_id": item.id, "record_kind": data.kind, "finalized": data.finalized})
    db.session.commit()
    return proceeding_json(item, case), 201


@workflow_api.post("/proceedings/<int:proceeding_id>/milestones")
@authenticated
def create_milestone(proceeding_id):
    item, case = proceeding_or_404(proceeding_id, "coordinate")
    data = parse(MilestoneInput)
    check_version(item, data.version)
    if data.kind not in MILESTONES:
        abort(422, description="Invalid milestone type.")
    recipient = db.session.get(User, data.recipient_id)
    if not recipient or not recipient.active or not db.session.scalar(select(Complaint.id).where(Complaint.id == case.id, scope(recipient))):
        abort(422, description="The responsible recipient must have active case access.")
    due, snapshot = data.due_at, {"confirmed": False, "administrative": bool(data.due_at), "name": "Policy confirmation required", "reason": data.reason, "version": "recorded-target-v1"}
    if due and due <= data.start_at:
        abort(422, description="Target date must follow the milestone start event.")
    if data.policy_id:
        policy = db.session.get(MilestonePolicy, data.policy_id)
        if not policy or policy.route not in (item.kind, "any") or policy.institution_type not in (item.institution_type, "any"):
            abort(422, description="Policy is not applicable to this route/institution.")
        if policy.effective_from.replace(tzinfo=timezone.utc) > data.start_at or policy.effective_until and policy.effective_until.replace(tzinfo=timezone.utc) <= data.start_at:
            abort(422, description="Policy was not effective at the recorded start event.")
        snapshot = {"id": policy.id, "name": policy.name, "version": policy.version, "source": policy.source, "clause": policy.clause,
                    "confirmed": policy.confirmed, "administrative": policy.administrative, "start_event": policy.start_event,
                    "pause_rule": policy.pause_rule, "calendar": policy.calendar, "mode": policy.mode, "minutes": policy.minutes}
        if policy.confirmed or policy.administrative:
            from .sla import calculate, Calendar
            from datetime import date
            calendar = policy.calendar
            due = calculate(data.start_at, policy.minutes, policy.mode, Calendar(timezone=calendar.get("timezone", "Asia/Kolkata"),
                            weekdays=tuple(calendar.get("weekdays", [0, 1, 2, 3, 4])), intervals=tuple(tuple(v) for v in calendar.get("intervals", [[9, 17]])),
                            holidays=frozenset(date.fromisoformat(d) for d in calendar.get("holidays", []))))
        else:
            due = None
    milestone = Milestone(proceeding_id=item.id, kind=data.kind, title=data.title, start_at=data.start_at,
                          due_at=due, original_due_at=due, policy_snapshot=snapshot, recipient_id=recipient.id)
    db.session.add(milestone)
    item.version += 1
    event(case, "milestone_created", f"Milestone recorded: {data.title}", data.reason, {"proceeding_id": item.id, "policy": snapshot, "due_at": iso(due)})
    db.session.commit()
    return proceeding_json(item, case), 201


@workflow_api.patch("/milestones/<int:milestone_id>")
@authenticated
def update_milestone(milestone_id):
    milestone = db.session.get(Milestone, milestone_id)
    if not milestone:
        abort(404)
    item, case = proceeding_or_404(milestone.proceeding_id, "coordinate")
    data = parse(MilestoneChange)
    if data.version != milestone.revision:
        abort(409, description="Milestone changed; refresh before recalculating.")
    before = iso(milestone.due_at)
    if data.completed:
        milestone.completed_at, milestone.state = now(), "completed"
    else:
        if not data.due_at or not data.due_at.tzinfo or data.due_at <= milestone.start_at.replace(tzinfo=timezone.utc):
            abort(422, description="Record a timezone-aware recalculated target after the start event.")
        milestone.due_at = data.due_at
        milestone.policy_snapshot = {**milestone.policy_snapshot, "administrative": True, "recalculation_reason": data.reason, "original_policy_preserved": True}
    milestone.revision += 1
    item.version += 1
    event(case, "milestone_revised", "Milestone completion/recalculation recorded", data.reason,
          {"milestone_id": milestone.id, "previous_due_at": before, "due_at": iso(milestone.due_at), "original_due_at": iso(milestone.original_due_at)})
    db.session.commit()
    return {"ok": True}


@workflow_api.post("/proceedings/<int:proceeding_id>/compliance")
@authenticated
def create_compliance(proceeding_id):
    item, case = proceeding_or_404(proceeding_id)
    if not allowed(case, "case.compliance"):
        abort(403, description="Compliance coordination permission required.")
    data = parse(ComplianceInput)
    check_version(item, data.version)
    record = db.session.get(ProceedingRecord, data.direction_record_id)
    verifier = db.session.get(User, data.verifier_id)
    if not record or record.proceeding_id != item.id or not record.finalized:
        abort(422, description="Compliance must refer to an authorized finalized direction/report.")
    if not verifier or not verifier.active or "verifier" not in roles(verifier) or not db.session.scalar(select(Complaint.id).where(Complaint.id == case.id, scope(verifier))):
        abort(422, description="Choose an active independently authorized verifier with case access.")
    if verifier.id == data.respondent_user_id:
        abort(422, description="A respondent cannot be the assigned verifier.")
    db.session.add(ComplianceItem(proceeding_id=item.id, direction_record_id=record.id, title=data.title,
                                 responsible_party=data.responsible_party, verifier_id=verifier.id, respondent_user_id=data.respondent_user_id))
    item.stage, item.version = "compliance_review", item.version + 1
    event(case, "compliance_created", f"Compliance item: {data.title}", data.reason, {"proceeding_id": item.id, "verifier_id": verifier.id})
    db.session.commit()
    return proceeding_json(item, case), 201


@workflow_api.post("/compliance/<int:item_id>/submissions")
@authenticated
def submit_compliance(item_id):
    item = db.session.get(ComplianceItem, item_id)
    if not item:
        abort(404)
    proceeding, case = proceeding_or_404(item.proceeding_id)
    if not allowed(case, "case.compliance"):
        abort(403, description="Only an authorized recording officer can record respondent correspondence.")
    data = parse(SubmissionInput)
    check_version(item, data.version)
    evidence_or_422(case, data.attachment_id, proceeding, clean=False)
    db.session.add(ComplianceSubmission(item_id=item.id, attachment_id=data.attachment_id, submitted_by=g.user.id,
                                       submitting_party=data.submitting_party, note=data.reason))
    item.state = "evidence_submitted"
    item.version += 1
    event(case, "compliance_submitted", "Compliance evidence submitted; independent verification pending", data.reason, {"item_id": item.id})
    notify(item.verifier_id, case, "compliance", f"{case.reference}: compliance evidence awaits your independent verification.", f"compliance:{item.id}:{item.version}:{item.verifier_id}")
    db.session.commit()
    return {"ok": True}, 201


@workflow_api.post("/compliance/<int:item_id>/verify")
@authenticated
def verify_compliance(item_id):
    item = db.session.get(ComplianceItem, item_id)
    if not item:
        abort(404)
    proceeding, case = proceeding_or_404(item.proceeding_id)
    data = parse(VerificationInput)
    check_version(item, data.version)
    submission = db.session.get(ComplianceSubmission, data.submission_id)
    if "verifier" not in roles() or item.verifier_id != g.user.id or item.respondent_user_id == g.user.id:
        abort(403, description="The independently assigned verifier must record this decision.")
    if not submission or submission.item_id != item.id or submission.submitted_by == g.user.id:
        abort(403, description="A submitter cannot verify its own compliance evidence.")
    if data.outcome not in ("verified", "disputed", "incomplete"):
        abort(422, description="Choose verified, disputed or incomplete.")
    evidence_or_422(case, submission.attachment_id, proceeding)
    db.session.add(ComplianceVerification(item_id=item.id, submission_id=submission.id, verifier_id=g.user.id,
                                          outcome=data.outcome, observations=data.observations, reason=data.reason))
    item.state, item.version = data.outcome, item.version + 1
    event(case, "compliance_verified", f"Compliance outcome: {data.outcome}", data.reason,
          {"item_id": item.id, "submission_id": submission.id, "observations": data.observations})
    db.session.commit()
    return {"ok": True}


@workflow_api.post("/proceedings/<int:proceeding_id>/packets")
@authenticated
def prepare_packet(proceeding_id):
    item, case = proceeding_or_404(proceeding_id, "packet")
    data = parse(PacketInput)
    check_version(item, data.version)
    documents = [evidence_or_422(case, attachment_id, item) for attachment_id in sorted(set(data.attachment_ids))]
    manifest = {"case_reference": case.reference, "case_version": case.version, "proceeding_version": item.version,
                "authority": item.external_authority, "generated_at": iso(now()), "status": "Prepared only; no dispatch or legal filing is implied",
                "documents": [{"id": d.id, "filename": d.filename, "sha256": d.checksum, "size": d.size} for d in documents]}
    packet = DispatchPacket(proceeding_id=item.id, created_by=g.user.id, manifest=manifest)
    db.session.add(packet)
    item.version += 1
    event(case, "packet_prepared", "Reviewed case packet prepared; not dispatched", data.reason, {"proceeding_id": item.id, "document_count": len(documents)})
    db.session.commit()
    return proceeding_json(item, case), 201


@workflow_api.get("/packets/<int:packet_id>/download")
@authenticated
def download_packet(packet_id):
    packet = db.session.get(DispatchPacket, packet_id)
    if not packet:
        abort(404)
    item, case = proceeding_or_404(packet.proceeding_id, "packet")
    from .security import require_recent_auth
    require_recent_auth()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(packet.manifest, indent=2))
        for entry in packet.manifest["documents"]:
            evidence = evidence_or_422(case, entry["id"], item)
            if evidence.checksum != entry["sha256"]:
                abort(409, description="Packet evidence changed. Prepare a new reviewed packet.")
            from .storage import read
            archive.writestr(f"{evidence.id}-{evidence.filename}", read(evidence))
    event(case, "packet_downloaded", "Authorized case packet downloaded", changes={"packet_id": packet.id})
    db.session.commit()
    output.seek(0)
    return send_file(output, mimetype="application/zip", as_attachment=True, download_name=f"{case.reference}-packet-{packet.id}.zip")


@workflow_api.post("/packets/<int:packet_id>/dispatch")
@authenticated
def record_dispatch(packet_id):
    packet = db.session.get(DispatchPacket, packet_id)
    if not packet:
        abort(404)
    item, case = proceeding_or_404(packet.proceeding_id)
    if not allowed(case, "case.packet"):
        abort(403, description="A bureau coordinator must review and authorize actual dispatch.")
    data = parse(DispatchInput)
    check_version(packet, data.version)
    if packet.state != "prepared" or not item.destination_validated:
        abort(422, description="Dispatch requires a prepared packet and validated destination.")
    if not data.occurred_at.tzinfo or data.occurred_at > now():
        abort(422, description="Record the actual past dispatch timestamp with its timezone.")
    evidence_or_422(case, data.delivery_attachment_id, item)
    packet.state, packet.reviewed_by = "dispatched", g.user.id
    packet.dispatched_at, packet.dispatch_channel, packet.dispatch_reference = data.occurred_at, data.channel, data.reference
    packet.delivery_attachment_id = data.delivery_attachment_id
    event(case, "packet_dispatched", "Actual external dispatch recorded", data.reason, {"packet_id": packet.id, "reference": data.reference})
    db.session.commit()
    return {"ok": True}


@workflow_api.post("/packets/<int:packet_id>/acknowledge")
@authenticated
def acknowledge_packet(packet_id):
    packet = db.session.get(DispatchPacket, packet_id)
    if not packet:
        abort(404)
    item, case = proceeding_or_404(packet.proceeding_id, "coordinate")
    data = parse(AcknowledgeInput)
    check_version(packet, data.version)
    if packet.state != "dispatched" or not data.occurred_at.tzinfo or data.occurred_at > now() or data.occurred_at < packet.dispatched_at.replace(tzinfo=timezone.utc):
        abort(422, description="Acknowledgement must follow an actual dispatch.")
    packet.state, packet.acknowledged_at, packet.acknowledgement_reference = "acknowledged", data.occurred_at, data.reference
    event(case, "dispatch_acknowledged", "Receiving authority acknowledgement recorded", data.reason, {"packet_id": packet.id})
    db.session.commit()
    return {"ok": True}


def validate_disposition(case, data):
    evidence_or_422(case, data.outcome_document_id)
    if len(data.communication.strip()) < 10:
        abort(422, description="Record the disposition communication and recipient/reference.")
    proceedings = db.session.scalars(select(Proceeding).where(Proceeding.complaint_id == case.id)).all()
    outstanding = db.session.scalar(select(ComplianceItem.id).where(ComplianceItem.proceeding_id.in_([p.id for p in proceedings]), ComplianceItem.state != "verified").limit(1))
    if outstanding:
        abort(422, description="Outstanding compliance must be independently verified before disposal.")
    if any(p.state == "active" for p in proceedings) and not data.external_continues:
        abort(422, description="Confirm and explain that linked external proceedings continue after administrative disposal, or record their conclusion first.")
    if db.session.scalar(select(ComplianceItem.id).where(ComplianceItem.proceeding_id.in_([p.id for p in proceedings]), ComplianceItem.respondent_user_id == g.user.id)):
        abort(403, description="A respondent cannot dispose the case containing its own compliance item.")


@workflow_api.post("/proceedings/<int:proceeding_id>/conclude")
@authenticated
def conclude_proceeding(proceeding_id):
    item, case = proceeding_or_404(proceeding_id, "coordinate")
    data = parse(Change)
    check_version(item, data.version)
    if not db.session.scalar(select(ProceedingRecord.id).where(ProceedingRecord.proceeding_id == item.id, ProceedingRecord.finalized.is_(True))):
        abort(422, description="Record an authorized final document before concluding this proceeding record.")
    item.state = "concluded"
    event(case, "proceeding_concluded", "External proceeding record concluded; no legal finality asserted", data.reason, {"proceeding_id": item.id})
    db.session.commit()
    return {"ok": True}
