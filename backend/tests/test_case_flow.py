from datetime import timedelta
import pytest
from sqlalchemy import select
from app.models import db, User, CaseWorkflow, CaseWorkflowReport, CaseConflict, Notification, Pair, now
from conftest import login, approved_test_evidence
from test_public_intake import public_login, details
from test_matching import DeterministicModels
from app.matching import process


def provision(app):
    with app.app_context():
        users = {r: db.session.scalar(select(User).where(User.role == r)) for r in
                 ('officer', 'lead', 'committee', 'reviewer', 'verifier', 'auditor', 'executive')}
        faculty = User(name='Appointed faculty reviewer', email='faculty-review@example.com', role='faculty_reviewer',
                       password_hash=users['officer'].password_hash)
        alternate = User(name='Independent appeal executive', email='appeal-executive@example.com', role='executive',
                         password_hash=users['officer'].password_hash)
        db.session.add_all([faculty, alternate]); db.session.commit()
        users['faculty_reviewer'] = faculty
        result = {r: {'id': u.id, 'email': u.email} for r, u in users.items()}
        result['alternate'] = {'id': alternate.id, 'email': alternate.email}
        app.config['PUBLIC_INTAKE_OWNER_ID'] = users['officer'].id
    return result


def acting(app, users, role):
    client = app.test_client()
    return client, login(client, users[role]['email'])


def post_stage(client, headers, cid, endpoint='advance', **extra):
    version = client.get(f'/api/complaints/{cid}/case-workflow').json['version']
    return client.post(f'/api/complaints/{cid}/case-workflow/{endpoint}', headers=headers,
                      json={'version': version, 'report': 'Reviewed the recorded evidence and submitted a reasoned stage assessment.', **extra})


def assign(app, users, cid, **extra):
    admin = app.test_client(); headers = login(admin, 'admin@onecase.demo')
    version = admin.get(f'/api/complaints/{cid}/case-workflow').json['version']
    response = admin.post(f'/api/complaints/{cid}/case-workflow/team', headers=headers, json={
        'version': version, 'reason': 'Competent approval of case-bound responsibilities', 'approval_reference': 'APPROVAL-TEST-2026',
        **{r + '_id': u['id'] for r, u in users.items() if r not in ('officer', 'alternate')}, **extra})
    assert response.status_code == 200, response.json


@pytest.mark.parametrize('kind', ['student', 'parent', 'faculty', 'staff', 'other'])
def test_all_complainants_follow_reports_verification_decision_and_appeal(app, kind):
    users = provision(app)
    public = app.test_client(); headers = public_login(public, kind)
    case = public.post('/api/intake/complaints', headers=headers, json=details()).json
    cid = case['id']
    proof = approved_test_evidence(app, cid)
    assert case['handling_stage'] == 'initial_review'
    assign(app, users, cid)
    people = {r: acting(app, users, r) for r in users}
    officer, auth = people['officer']
    assert post_stage(officer, auth, cid).status_code == 403
    assert officer.post(f'/api/complaints/{cid}/status', headers=auth,
                        json={'version': case['version'], 'status': 'disposed', 'reason': 'Attempt to bypass the handling stages'}).status_code in (403, 409)
    outsider = app.test_client(); public_login(outsider, email='outsider@example.com')
    assert outsider.get(f'/api/complaints/{cid}/case-workflow').status_code == 404
    for r in ('faculty_reviewer', 'officer'):
        c, h = people[r]; result = post_stage(c, h, cid, report=(
            'The faculty reports that this complaint is false or already resolved; the officer must independently examine that claim.'
            if r == 'faculty_reviewer' else 'The officer reviewed the initial recommendation and requires independent investigation.'))
        assert result.status_code == 200, result.json
        if r == 'faculty_reviewer':
            assert result.json['stage'] == 'officer_triage'
    c, h = people['lead']
    blocked = post_stage(c, h, cid)
    assert blocked.status_code == 422 and 'committee' in blocked.json['error']['message']
    c, h = people['committee']; assert post_stage(c, h, cid, 'reports').status_code == 200
    c, h = people['lead']; assert post_stage(c, h, cid).status_code == 200
    c, h = people['reviewer']; assert post_stage(c, h, cid, 'reports', evidence_ids=[proof]).status_code == 200
    c, h = people['verifier']; assert post_stage(c, h, cid).status_code == 422  # auditor is mandatory for fee refunds
    c, h = people['auditor']; assert post_stage(c, h, cid, 'reports', evidence_ids=[proof]).status_code == 200
    c, h = people['verifier']; assert post_stage(c, h, cid, evidence_ids=[proof]).status_code == 200
    executive, eh = people['executive']
    assert post_stage(executive, eh, cid).status_code == 422  # no outcome proof or communication
    done = post_stage(executive, eh, cid, outcome_document_id=proof, communication='Outcome communicated to the complainant through portal reference TEST-001.')
    assert done.status_code == 200, done.json
    assert done.json['stage'] == 'resolved'
    public_flow = public.get(f'/api/complaints/{cid}/case-workflow').json
    assert public_flow['can_appeal'] and public_flow['reports'] == public_flow['report_history'] == []
    closed = public.get(f'/api/complaints/{cid}').json
    assert closed['status'] == 'disposed' and closed['reports']
    path = f"/api/complaints/{cid}/reports/{closed['reports'][0]['id']}.pdf"
    frozen = public.get(path).data
    assert frozen.startswith(b'%PDF-')
    assert post_stage(public, {}, cid, 'appeal').status_code == 403  # CSRF preserved
    appealed = post_stage(public, headers, cid, 'appeal')
    assert appealed.status_code == 201 and appealed.json['stage'] == 'appeal_review'
    assert public.get(path).data == frozen
    assert public.get(f'/api/complaints/{cid}').json['status'] == 'under_review'
    if kind == 'student':
        for r, endpoint in [('committee','reports'), ('lead','advance'), ('reviewer','reports'), ('auditor','reports'), ('verifier','advance')]:
            c,h = people[r]; result = post_stage(c,h,cid,endpoint,evidence_ids=[proof])
            assert result.status_code == 200, result.json
        same = post_stage(executive,eh,cid,outcome_document_id=proof,communication='Appeal decision reference TEST-002 communicated to the complainant.')
        assert same.status_code == 403
        assign(app,users,cid,executive_id=users['alternate']['id'])
        c,h = people['alternate']; result = post_stage(c,h,cid,outcome_document_id=proof,communication='Independent appeal decision TEST-003 communicated to the complainant.')
        assert result.status_code == 200, result.json


def test_team_scope_conflicts_expiry_independence_and_report_privacy(app):
    users = provision(app)
    public = app.test_client(); ph = public_login(public)
    cid = public.post('/api/intake/complaints', headers=ph, json=details()).json['id']
    faculty, fh = acting(app, users, 'faculty_reviewer')
    assert faculty.get(f'/api/complaints/{cid}').status_code == 404
    assign(app,users,cid)
    assert faculty.get(f'/api/complaints/{cid}').status_code == 200
    version = faculty.get(f'/api/complaints/{cid}/case-workflow').json['version']
    assert post_stage(faculty,fh,cid,'reports',report='Private faculty assessment only for the handling team.').status_code == 200
    assert 'Private faculty assessment' not in str(public.get(f'/api/complaints/{cid}/actions').json)
    assert faculty.post(f'/api/complaints/{cid}/case-workflow/reports', headers=fh,
                        json={'version':version,'report':'Stale request should not overwrite a newer report.'}).status_code == 409
    assert faculty.get(f'/api/complaints/{cid}/case-workflow/candidates').status_code == 403
    with app.app_context():
        flow = db.session.get(CaseWorkflow,cid); flow.access_until = now() - timedelta(seconds=1); db.session.commit()
    assert faculty.get(f'/api/complaints/{cid}').status_code == 404
    assign(app,users,cid)
    with app.app_context():
        db.session.add(CaseConflict(complaint_id=cid,user_id=users['faculty_reviewer']['id'],reason='Recorded conflict',decision_reference='CONFLICT-001',
                                    recorded_by=db.session.scalar(select(User.id).where(User.role=='admin'))))
        db.session.commit()
    assert faculty.get(f'/api/complaints/{cid}').status_code == 404


def test_overlap_alerts_both_assigned_officers_without_other_case_content(app):
    with app.app_context():
        assert process(1,1,DeterministicModels()) == 'completed'
        pair = db.session.scalar(select(Pair).where(Pair.case_a_id==1,Pair.case_b_id==2))
        owner_alerts = db.session.scalars(select(Notification).where(Notification.dedup_key.like(f'pair-owner:{pair.id}:%'))).all()
        assert {n.complaint_id for n in owner_alerts} == {1,2}
        from app.models import Complaint
        for note in owner_alerts:
            own = db.session.get(Complaint,note.complaint_id)
            other = db.session.get(Complaint,2 if own.id==1 else 1)
            assert note.user_id == own.owner_id and other.reference not in note.message and other.description not in note.message
        before = len(owner_alerts)
        process(1,1,DeterministicModels())
        assert len(db.session.scalars(select(Notification).where(Notification.dedup_key.like(f'pair-owner:{pair.id}:%'))).all()) == before
