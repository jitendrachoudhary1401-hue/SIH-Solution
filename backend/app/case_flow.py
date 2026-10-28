"""Internal complaint handling. Human stage decisions preserve external proceedings."""
from datetime import timedelta, timezone
from flask import Blueprint, abort, g
from pydantic import Field
from sqlalchemy import select
from .models import db, now, iso, User, Complaint, CaseWorkflow, CaseWorkflowReport, CaseConflict, Attachment
from .auth import authenticated, roles, PUBLIC_ROLES, ROLES, case_or_404, check_version, document_allowed, has_content
from .api import Input, parse, event, notify
from .documents import evidence_available

case_flow_api = Blueprint('case_flow', __name__)
SLOTS = ('faculty_reviewer', 'officer', 'lead', 'committee', 'reviewer', 'verifier', 'auditor', 'executive')
LABELS = {'initial_review': 'Initial faculty / grievance review', 'officer_triage': 'Officer review and triage',
          'committee_review': 'Specialized lead and committee review', 'investigation': 'Fact investigation and verification',
          'executive_decision': 'Executive decision', 'resolved': 'Outcome communicated', 'appeal_review': 'Independent appeal review'}
ORDER = ['initial_review', 'officer_triage', 'committee_review', 'investigation', 'executive_decision', 'resolved']
REQUIRED = {'initial_review': ['faculty_reviewer'], 'officer_triage': ['officer'],
            'committee_review': ['lead', 'committee'], 'appeal_review': ['lead', 'committee'],
            'investigation': ['reviewer', 'verifier'], 'executive_decision': ['executive'], 'resolved': []}
ACTOR = {'initial_review': 'faculty_reviewer', 'officer_triage': 'officer', 'committee_review': 'lead',
         'appeal_review': 'lead', 'investigation': 'verifier', 'executive_decision': 'executive'}


class Team(Input):
    version: int
    reason: str = Field(min_length=5, max_length=1000)
    approval_reference: str = Field(min_length=5, max_length=200)
    faculty_reviewer_id: int | None = Field(default=None, gt=0)
    lead_id: int | None = Field(default=None, gt=0)
    committee_id: int | None = Field(default=None, gt=0)
    reviewer_id: int | None = Field(default=None, gt=0)
    verifier_id: int | None = Field(default=None, gt=0)
    auditor_id: int | None = Field(default=None, gt=0)
    executive_id: int | None = Field(default=None, gt=0)
    auditor_required: bool = False


class Report(Input):
    version: int
    report: str = Field(min_length=20, max_length=10000)
    evidence_ids: list[int] = Field(default_factory=list, max_length=30)


class Advance(Report):
    outcome: str = 'resolved'
    outcome_document_id: int | None = Field(default=None, gt=0)
    communication: str = Field(default='', max_length=2000)
    external_continues: bool = False


def start(case):
    flow = CaseWorkflow(complaint_id=case.id, stage='initial_review', cycle=1, version=1,
                        officer_id=case.owner_id, access_until=now() + timedelta(days=90),
                        auditor_required=case.category in ('Fee refund', 'Infrastructure'), public_decision='')
    db.session.add(flow)
    case.next_action = 'Appoint a faculty / grievance reviewer for initial review'
    return flow


def eligible(case, role, user_id):
    user = db.session.get(User, user_id) if user_id else None
    return bool(user and user.active and user.role in ROLES and (role in roles(user) or role == 'officer' and 'lead' in roles(user))
                and user.id != case.submitter_user_id and user.is_demo == bool(case.owner.is_demo)
                and (role not in ('officer', 'lead') or user.bureau_id)
                and not db.session.scalar(select(CaseConflict.id).where(CaseConflict.complaint_id == case.id,
                                            CaseConflict.user_id == user.id, CaseConflict.resolved_at.is_(None))))


def manager(case):
    return g.user.role not in PUBLIC_ROLES and (
        'admin' in roles() or 'officer' in roles() and case.owner_id == g.user.id
        or 'lead' in roles() and case.bureau_id == g.user.bureau_id)


def required(flow):
    return REQUIRED[flow.stage] + (['auditor'] if flow.stage == 'investigation' and flow.auditor_required else [])


def assigned(flow, case, role):
    return (flow.access_until.replace(tzinfo=timezone.utc) > now()
            and eligible(case, role, getattr(flow, role + '_id')))


def actor_slot(flow, case):
    return next((r for r in required(flow) if getattr(flow, r + '_id') == g.user.id and assigned(flow, case, r)), None)


def reports(flow):
    return db.session.scalars(select(CaseWorkflowReport).where(CaseWorkflowReport.complaint_id == flow.complaint_id,
                       CaseWorkflowReport.cycle == flow.cycle, CaseWorkflowReport.stage == flow.stage)
                       .order_by(CaseWorkflowReport.id)).all()


def missing_reports(flow, case):
    saved = {(r.role, r.actor_id) for r in reports(flow)}
    return [role for role in required(flow) if not assigned(flow, case, role)
            or (role, getattr(flow, role + '_id')) not in saved]


def announce(case, flow):
    recipients = {getattr(flow, r + '_id') for r in required(flow) if assigned(flow, case, r)}
    if eligible(case, 'officer', case.owner_id):
        recipients.add(case.owner_id)
    if case.submitter_user_id:
        recipients.add(case.submitter_user_id)
    for uid in recipients:
        notify(uid, case, 'workflow', f'{case.reference}: {LABELS[flow.stage]}.',
               f'workflow:{case.id}:{flow.cycle}:{flow.version}:{flow.stage}:{uid}')


def serialize(case, flow):
    if not flow:
        return {'managed': False}
    public = g.user.role in PUBLIC_ROLES or not has_content(case)
    stage_reports = reports(flow)
    return {'managed': True, 'stage': flow.stage, 'stage_label': LABELS[flow.stage], 'cycle': flow.cycle,
            'version': flow.version, 'steps': [{'stage': s, 'label': LABELS[s]} for s in ORDER],
            'outcome': flow.outcome, 'public_decision': flow.public_decision,
            'auditor_required': flow.auditor_required, 'access_until': iso(flow.access_until),
            'team': [{'role': r, 'user_id': getattr(flow, r + '_id'),
                      'name': db.session.get(User, getattr(flow, r + '_id')).name if getattr(flow, r + '_id') else 'Awaiting assignment'} for r in SLOTS],
            'can_manage': manager(case), 'can_report': not public and bool(actor_slot(flow, case)),
            'can_advance': not public and actor_slot(flow, case) == ACTOR.get(flow.stage),
            'can_appeal': case.submitter_user_id == g.user.id and flow.stage == 'resolved',
            'missing_reports': [] if public else missing_reports(flow, case),
            'reports': [] if public else [{'id': r.id, 'role': r.role, 'actor_id': r.actor_id,
                          'report': r.report, 'evidence_ids': r.evidence_ids, 'created_at': iso(r.created_at)} for r in stage_reports],
            'report_history': [] if public else [{'id': r.id, 'stage': r.stage, 'cycle': r.cycle, 'role': r.role,
                          'report': r.report, 'created_at': iso(r.created_at)} for r in db.session.scalars(
                          select(CaseWorkflowReport).where(CaseWorkflowReport.complaint_id == case.id).order_by(CaseWorkflowReport.id))]}


def load(case_id):
    case = case_or_404(case_id)
    flow = db.session.get(CaseWorkflow, case_id)
    if not flow:
        abort(409, description='This is a legacy case. An authorized officer may enable the handling workflow.')
    return case, flow


@case_flow_api.get('/complaints/<int:case_id>/case-workflow')
@authenticated
def detail(case_id):
    case = case_or_404(case_id)
    return serialize(case, db.session.get(CaseWorkflow, case_id))


@case_flow_api.post('/complaints/<int:case_id>/case-workflow/start')
@authenticated
def enable(case_id):
    case = case_or_404(case_id)
    if not manager(case):
        abort(403)
    data = parse(Report)
    check_version(case, data.version)
    if case.status == 'disposed' or db.session.get(CaseWorkflow, case_id):
        abort(409, description='Use an active legacy complaint that has no handling workflow.')
    flow = start(case)
    event(case, 'workflow_started', 'Structured complaint handling enabled', 'Initial review required.')
    case.version += 1
    db.session.commit()
    return serialize(case, flow), 201


@case_flow_api.get('/complaints/<int:case_id>/case-workflow/candidates')
@authenticated
def candidates(case_id):
    case = case_or_404(case_id)
    if not manager(case):
        abort(403)
    users = db.session.scalars(select(User).where(User.active.is_(True)).order_by(User.name)).all()
    return {'items': [{'id': u.id, 'name': u.name, 'roles': [r for r in SLOTS if eligible(case, r, u.id)]}
                      for u in users if any(eligible(case, r, u.id) for r in SLOTS)]}


@case_flow_api.post('/complaints/<int:case_id>/case-workflow/team')
@authenticated
def team(case_id):
    case, flow = load(case_id)
    if not manager(case):
        abort(403)
    from .security import require_recent_auth
    require_recent_auth()
    data = parse(Team)
    check_version(flow, data.version)
    if flow.stage == 'resolved':
        abort(409, description='The completed cycle is preserved. A submitted appeal opens a new review cycle.')
    for role in SLOTS:
        if role == 'officer':
            continue  # accountable officer changes use the existing audited transfer endpoint
        field = role + '_id'
        if field in data.model_fields_set:
            uid = getattr(data, field)
            if uid and not eligible(case, role, uid):
                abort(422, description=f'Choose an approved, unconflicted {role.replace("_", " ")} in this workspace.')
            setattr(flow, field, uid)
    ids = [getattr(flow, r + '_id') for r in SLOTS if getattr(flow, r + '_id')]
    if len(ids) != len(set(ids)):
        abort(422, description='Assign a different person to each handling role to preserve independent review.')
    if 'auditor_required' in data.model_fields_set:
        flow.auditor_required = data.auditor_required or case.category in ('Fee refund', 'Infrastructure')
    flow.access_until = now() + timedelta(days=90)
    flow.version += 1
    event(case, 'workflow_team_assigned', 'Case handling team appointed', 'Approved case-bound responsibilities recorded.',
          {'approval_reference': data.approval_reference, 'reason': data.reason,
           'team': {r: getattr(flow, r + '_id') for r in SLOTS}, 'access_until': iso(flow.access_until)})
    announce(case, flow)
    db.session.commit()
    return serialize(case, flow)


def save_report(case, flow, data):
    role = actor_slot(flow, case)
    if not role:
        abort(403, description='Only the currently appointed person for this stage can submit its report.')
    for aid in data.evidence_ids:
        item = db.session.get(Attachment, aid)
        if not item or item.complaint_id != case.id or not document_allowed(case, item) or not evidence_available(item):
            abort(422, description='Use available evidence belonging to this complaint and permitted to your role.')
    db.session.add(CaseWorkflowReport(complaint_id=case.id, cycle=flow.cycle, stage=flow.stage, role=role,
                                    actor_id=g.user.id, report=data.report, evidence_ids=data.evidence_ids))
    event(case, 'workflow_reported', f'{role.replace("_", " ").title()} submitted a stage report',
          'A report was recorded for the appointed handling team.', {'stage': flow.stage, 'cycle': flow.cycle})


@case_flow_api.post('/complaints/<int:case_id>/case-workflow/reports')
@authenticated
def report(case_id):
    case, flow = load(case_id)
    data = parse(Report)
    check_version(flow, data.version)
    save_report(case, flow, data)
    flow.version += 1
    announce(case, flow)
    db.session.commit()
    return serialize(case, flow)


@case_flow_api.post('/complaints/<int:case_id>/case-workflow/advance')
@authenticated
def advance(case_id):
    case, flow = load(case_id)
    data = parse(Advance)
    check_version(flow, data.version)
    if actor_slot(flow, case) != ACTOR.get(flow.stage) or flow.stage == 'resolved':
        abort(403, description='Only the appointed stage coordinator can advance this complaint.')
    if flow.stage == 'executive_decision':
        from .security import require_recent_auth
        require_recent_auth()
    save_report(case, flow, data)
    db.session.flush()
    missing = missing_reports(flow, case)
    if missing:
        abort(422, description='Reports or valid appointments are still required from: ' + ', '.join(missing))
    previous = flow.stage
    next_stage = {'initial_review': 'officer_triage', 'officer_triage': 'committee_review',
                  'committee_review': 'investigation', 'appeal_review': 'investigation', 'investigation': 'executive_decision'}
    if previous in next_stage:
        target = next_stage[previous]
        if any(not assigned(flow, case, r) for r in REQUIRED[target] + (['auditor'] if target == 'investigation' and flow.auditor_required else [])):
            abort(422, description='Appoint the required team for the next stage before handing over.')
        flow.stage = target
        if case.status == 'received':
            case.status = 'under_review'
    else:
        if data.outcome not in ('resolved', 'not_upheld'):
            abort(422, description='Choose resolved or not upheld and give a reasoned outcome.')
        earlier_decider = db.session.scalar(select(CaseWorkflowReport.id).where(
            CaseWorkflowReport.complaint_id == case.id, CaseWorkflowReport.role == 'executive',
            CaseWorkflowReport.stage == 'executive_decision', CaseWorkflowReport.cycle < flow.cycle,
            CaseWorkflowReport.actor_id == g.user.id))
        if earlier_decider:
            abort(403, description='An appeal requires a different executive decision-maker.')
        from .workflow import validate_disposition
        validate_disposition(case, data)
        old = case.status
        case.status, flow.stage, flow.outcome = 'disposed', 'resolved', data.outcome
        flow.public_decision = data.report
        closure = event(case, 'status_changed', 'Executive outcome communicated', data.report,
                        {'status': {'before': old, 'after': 'disposed'}, 'outcome': data.outcome,
                         'outcome_document_id': data.outcome_document_id, 'communication': data.communication,
                         'deadline_at': iso(case.due_at), 'paused_at': iso(case.paused_at), 'deadline_policy': case.deadline_policy})
        from .complaint_reports import freeze_report
        freeze_report(case, closure)
    flow.version += 1
    case.version += 1
    case.next_action = LABELS[flow.stage]
    event(case, 'workflow_advanced', f'Handling stage: {LABELS[flow.stage]}',
          'The appointed coordinator completed the stage handover.', {'before': previous, 'after': flow.stage, 'cycle': flow.cycle})
    announce(case, flow)
    db.session.commit()
    return serialize(case, flow)


@case_flow_api.post('/complaints/<int:case_id>/case-workflow/appeal')
@authenticated
def appeal(case_id):
    case, flow = load(case_id)
    if case.submitter_user_id != g.user.id:
        abort(403, description='Only the complainant may submit this appeal request.')
    data = parse(Report)
    check_version(flow, data.version)
    if flow.stage != 'resolved' or case.status != 'disposed':
        abort(409, description='An appeal can be requested after an outcome is communicated.')
    flow.cycle += 1
    flow.stage, flow.outcome, case.status = 'appeal_review', None, 'under_review'
    flow.version += 1
    case.version += 1
    case.next_action = 'Appoint an independent appeal team and executive authority'
    db.session.add(CaseWorkflowReport(complaint_id=case.id, cycle=flow.cycle, stage='appeal_review',
                    role='complainant', actor_id=g.user.id, report=data.report, evidence_ids=[]))
    event(case, 'reopened', 'Complainant requested review of the outcome', 'Appeal request recorded for internal review.',
          {'status': {'before': 'disposed', 'after': 'under_review'}, 'cycle': flow.cycle})
    announce(case, flow)
    db.session.commit()
    return serialize(case, flow), 201
