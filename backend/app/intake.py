"""Authenticated public intake. Identity and ownership are always server-derived."""
import json
import secrets
from uuid import uuid4
from flask import Blueprint, abort, current_app, g, request
from pydantic import Field
from sqlalchemy import select
from .api import Input, parse, CATEGORIES, hasher, institution_json, case_json, event, enqueue, notify
from .auth import authenticated, PUBLIC_ROLES, SUBMITTER_ROLES, digest
from .models import db, User, Bureau, Institution, Complaint, Assignment, Idempotency, now

intake_api = Blueprint('intake', __name__)
CHANNELS = ['OneCase portal', 'Institutional portal reference', 'CPGRAMS reference', 'Ministry of Education reference']


class Submission(Input):
    institution_id: int | None = Field(default=None, gt=0)
    institution_name: str = Field(default='', max_length=200)
    region: str = Field(default='', max_length=80)
    category: str
    incident_location: str = Field(default='', max_length=200)
    issue_summary: str = Field(min_length=5, max_length=300)
    description: str = Field(min_length=20, max_length=20000)
    affected_person: str = Field(default='', max_length=150)
    representation_basis: str = Field(default='', max_length=1000)
    source_channel: str = 'OneCase portal'
    source_reference: str = Field(default='', max_length=150)
    declaration: bool


def stakeholder():
    if g.user.role not in SUBMITTER_ROLES:
        abort(403, description='Only students, parents, institution staff and faculty may register complaints. Review roles manage assigned cases.')


def intake_owner():
    if g.user.is_demo:
        owner = db.session.scalar(select(User).join(Bureau).where(User.is_demo.is_(True), User.role == 'officer', User.active.is_(True), Bureau.code == 'PUBLIC-DEMO'))
        if not owner:
            abort(409, description='The demo intake officer has not been provisioned.')
        return owner
    owner_id = current_app.config.get('PUBLIC_INTAKE_OWNER_ID')
    if owner_id:
        owner = db.session.get(User, owner_id)
        if not owner or not owner.active or owner.is_demo or owner.role not in ('officer', 'lead') or not owner.bureau_id:
            abort(409, description='The configured intake officer is unavailable. Contact the administrator.')
        return owner
    owner = db.session.scalar(select(User).where(User.email == 'public-intake@onecase.internal'))
    if not owner:
        bureau = db.session.scalar(select(Bureau).where(Bureau.code == 'INTAKE'))
        if not bureau:
            bureau = Bureau(code='INTAKE', name='Public complaint intake')
            db.session.add(bureau)
            db.session.flush()
        owner = User(name='Awaiting officer assignment', email='public-intake@onecase.internal',
                     role='intake', active=False, bureau_id=bureau.id, password_hash=hasher.hash(secrets.token_urlsafe(48)))
        db.session.add(owner)
        db.session.flush()
    if owner.role != 'intake' or owner.active or not owner.bureau_id:
        abort(409, description='The intake queue identity requires administrator configuration.')
    return owner


@intake_api.get('/intake/options')
@authenticated
def options():
    stakeholder()
    query = select(Institution).order_by(Institution.name)
    query = query.where(Institution.external_id == 'ONECASE-PUBLIC-DEMO') if g.user.is_demo else query.where((Institution.external_id.is_(None)) | (Institution.external_id != 'ONECASE-PUBLIC-DEMO'))
    term = request.args.get('q', '').strip()[:100]
    if term:
        query = query.where(Institution.name.ilike('%' + term + '%'))
    return {'institutions': [institution_json(i) for i in db.session.scalars(query.limit(100))],
            'categories': CATEGORIES, 'channels': CHANNELS, 'max_upload_bytes': current_app.config['MAX_UPLOAD_BYTES'],
            'max_files': current_app.config['DOCUMENT_LIMIT_PER_CASE']}


@intake_api.post('/intake/complaints')
@authenticated
def submit():
    stakeholder()
    data = parse(Submission)
    if not data.declaration or data.category not in CATEGORIES or data.source_channel not in CHANNELS:
        abort(422, description='Choose a valid category and source, and confirm the declaration.')
    if g.user.role == 'parent' and (not data.affected_person or len(data.representation_basis) < 5):
        abort(422, description='Provide the affected student name and your relationship or authority to represent them.')
    if data.source_channel != CHANNELS[0] and not data.source_reference:
        abort(422, description='Provide the reference issued by the source portal.')
    key = request.headers.get('Idempotency-Key', '')
    if not 8 <= len(key) <= 100:
        abort(422, description='A submission key is required.')
    fingerprint = digest(json.dumps(data.model_dump(), sort_keys=True))
    previous = db.session.scalar(select(Idempotency).where(Idempotency.user_id == g.user.id, Idempotency.key == key))
    if previous:
        if previous.digest != fingerprint:
            abort(409, description='This submission key was already used for different details.')
        return case_json(db.session.get(Complaint, previous.complaint_id), True)
    institution = db.session.get(Institution, data.institution_id) if data.institution_id else None
    if data.institution_id and not institution:
        abort(422, description='Institution unavailable. Search again or enter its details.')
    if g.user.is_demo and (not institution or institution.external_id != 'ONECASE-PUBLIC-DEMO'):
        abort(422, description='Demo submissions must use the synthetic demo institution.')
    if institution and not g.user.is_demo and institution.external_id == 'ONECASE-PUBLIC-DEMO':
        abort(422, description='Choose your actual institution.')
    if not institution:
        if len(data.institution_name) < 3 or len(data.region) < 2:
            abort(422, description='Provide the institution name and region.')
        institution = Institution(name=data.institution_name, region=data.region, address='', verified=False)
        db.session.add(institution)
        db.session.flush()
    owner = intake_owner()
    case = Complaint(reference=f'OC-{now().year}-{uuid4().hex.upper()}', institution_id=institution.id,
                     bureau_id=owner.bureau_id, owner_id=owner.id, submitter_user_id=g.user.id,
                     complainant_type=g.user.role, submitter_name=g.user.name,
                     affected_person=data.affected_person or g.user.name, representation_basis=data.representation_basis,
                     category=data.category, issue_summary=data.issue_summary, description=data.description, incident_location=data.incident_location,
                     source_channel=data.source_channel, source_reference=data.source_reference,
                     next_action='Intake review and assignment', deadline_policy='Deadline not yet assigned')
    db.session.add(case)
    db.session.flush()
    db.session.add(Assignment(complaint_id=case.id, bureau_id=owner.bureau_id, owner_id=owner.id, reason='Public portal intake'))
    from .case_flow import start
    start(case)
    db.session.add(Idempotency(user_id=g.user.id, key=key, digest=fingerprint, complaint_id=case.id))
    event(case, 'registered', 'Complaint registered', data.issue_summary,
          {'submitter': g.user.name, 'assigned_to': owner.name, 'source': data.source_channel})
    if owner.active:
        notify(owner.id, case, 'assignment', f'{case.reference} awaits your review.', f'intake:{case.id}:{owner.id}')
    for administrator in db.session.scalars(select(User).where(User.role == 'admin', User.active.is_(True))):
        notify(administrator.id, case, 'intake', f'{case.reference} registered by {g.user.name}. ' + ('Officer assignment required.' if not owner.active else 'Assigned for review.'), f'intake-admin:{case.id}:{administrator.id}')
    enqueue(case)
    db.session.commit()
    return case_json(case, True), 201
