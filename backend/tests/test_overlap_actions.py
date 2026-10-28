from datetime import timedelta
from sqlalchemy import select, func
from conftest import login
from app.models import (db, Complaint, User, Pair, Notification, CoordinationMember,
                        CoordinationGroup, CaseRecurrence, ActionEvent, now)
from app.api import enqueue, event
from app.matching import process
from test_matching import DeterministicModels
from app.overlap_actions import wording_similarity, text_key

TEXT = 'The tuition fee refund after timely withdrawal has still not been paid despite repeated written requests and receipt confirmation.'


def test_reported_extra_fee_paraphrases_create_visible_pair_and_officer_alert(app,client):
    a=record(app,'EXCESS',description='excess fees charged by college')
    b=record(app,'EXTRA',description='college charging extra fees')
    with app.app_context():
        enqueue(db.session.get(Complaint,b));db.session.commit()
    headers=login(client,'officer.rb@onecase.demo')
    pairs=client.get('/api/overlaps?state=pending').json['items']
    assert len(pairs)==1 and {pairs[0]['a']['id'],pairs[0]['b']['id']}=={a,b}
    assert pairs[0]['evidence']['wording']['normalized_match']
    assert set(pairs[0]['evidence']['shared_terms'])=={'extra','charge','fee'}
    notes=[n for n in client.get('/api/notifications').json['items'] if n['kind']=='overlap']
    assert len(notes)==2 and notes[0]['action_url']==f'/overlaps/{pairs[0]["id"]}'
    assert client.get('/api/dashboard/summary').json['pending_pairs']==1
    assert scan(client,headers)[0]['id']==pairs[0]['id']


def test_word_form_matching_preserves_issue_negations_and_numbers():
    for a,b in [('excess fees charged by college','college charging extra fees'),
                ('college has not refunded fees','fees not refunded by the college')]:
        assert wording_similarity(text_key(a),text_key(b))[0]>=.85
    for a,b in [('college charging extra fees','college has not refunded fees'),
                ('college charging extra fees','college not charging extra fees'),
                ('extra fees charged 5000','extra fees charged 1000')]:
        assert wording_similarity(text_key(a),text_key(b))[0]<.85


def test_paraphrases_at_different_locations_do_not_overlap(app,client):
    record(app,'EXCESS',description='excess fees charged by college')
    record(app,'EXTRA',description='college charging extra fees',location='Other campus')
    headers=login(client,'officer.rb@onecase.demo')
    assert scan(client,headers)==[]


def record(app, suffix, *, location='North campus accounts office', description=TEXT, status='received', received=None):
    with app.app_context():
        owner = db.session.scalar(select(User).where(User.email == 'officer.rb@onecase.demo'))
        case = Complaint(reference=f'TEST-OVERLAP-{suffix}', institution_id=1, bureau_id=owner.bureau_id,
                         owner_id=owner.id, category='Fee refund', description=description,
                         incident_location=location, received_at=received or now(), status=status)
        db.session.add(case)
        db.session.commit()
        return case.id


def scan(client, headers):
    result = client.post('/api/overlaps/scan', headers=headers, json={})
    assert result.status_code == 200, result.json
    return client.get('/api/overlaps?state=pending&limit=100').json['items']


def payload(pairs, action, **values):
    return dict(pairs=[{'id': p['id'], 'version': p['version']} for p in pairs], action=action,
                reason='Compared the facts and incident location in all listed complaints.', **values)


def test_immediate_alert_then_reject_all_preserves_complaints_and_deduplicates(app, client):
    a = record(app, 'A'); b = record(app, 'B')
    with app.app_context():
        enqueue(db.session.get(Complaint, b)); db.session.commit()
        assert db.session.scalar(select(func.count()).select_from(Pair)) == 1
        assert db.session.get(Complaint, b).matching_state == 'queued'  # Never pretend neural work ran.
    headers = login(client, 'officer.rb@onecase.demo')
    assert client.get('/api/auth/me').json['user']['capabilities']['overlaps']
    notes = client.get('/api/notifications').json['items']
    assert {n['complaint_id'] for n in notes if n['kind'] == 'overlap'} == {a,b}
    pairs = scan(client, headers)
    assert len(pairs) == 1 and pairs[0]['evidence']['method'] == 'text_similarity' and pairs[0]['can_review']
    assert len([n for n in client.get('/api/notifications').json['items'] if n['kind'] == 'overlap']) == 2
    assert client.post('/api/overlaps/bulk', json=payload(pairs,'reject')).status_code == 403
    result = client.post('/api/overlaps/bulk', headers=headers, json=payload(pairs,'reject'))
    assert result.status_code == 200 and result.json['updated'] == 1
    assert scan(client,headers) == []  # No re-alert for an unchanged rejected suggestion.
    for cid in (a,b):
        detail = client.get(f'/api/complaints/{cid}').json
        assert detail['status'] == 'received' and detail['coordination'] is None


def test_merge_all_creates_group_without_changing_original_workflow_deadlines_or_permissions(app,client):
    ids = [record(app,str(i)) for i in range(3)]
    headers = login(client,'officer.rb@onecase.demo'); pairs = scan(client,headers)
    before = [client.get(f'/api/complaints/{cid}').json for cid in ids]
    assert len(pairs) == 3
    result = client.post('/api/overlaps/bulk',headers=headers,json=payload(pairs,'merge',primary_complaint_id=ids[0]))
    assert result.status_code == 200, result.json
    for original in before:
        detail = client.get(f'/api/complaints/{original["id"]}').json
        assert {m['id'] for m in detail['coordination']['members']} == set(ids)
        assert detail['coordination']['primary_complaint_id'] == ids[0]
        for field in ('description','status','owner_id','received_at','due_at','handling_stage','content_revision'):
            assert detail[field] == original[field]
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(CoordinationGroup)) == 1
        assert db.session.scalar(select(func.count()).select_from(CoordinationMember)) == 3


def test_stale_or_unauthorized_batch_is_atomic(app,client):
    ids = [record(app,str(i)) for i in range(3)]
    headers = login(client,'officer.rb@onecase.demo'); pairs = scan(client,headers)
    invalid = payload(pairs,'reject'); invalid['pairs'][-1]['version'] += 1
    assert client.post('/api/overlaps/bulk',headers=headers,json=invalid).status_code == 409
    assert len(client.get('/api/overlaps?state=pending').json['items']) == 3
    other = app.test_client(); oh = login(other,'officer.pgrc@onecase.demo')
    assert other.post('/api/overlaps/bulk',headers=oh,json=payload(pairs,'reject')).status_code == 404
    with app.app_context():
        case = db.session.get(Complaint, ids[0]); case.incident_location = 'Different campus'; case.content_revision += 1; db.session.commit()
    assert client.post('/api/overlaps/bulk',headers=headers,json=payload(pairs,'merge',primary_complaint_id=ids[0])).status_code == 409
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(CoordinationMember)) == 0


def test_location_and_issue_are_both_required_for_text_and_neural_alerts(app,client):
    a=record(app,'A'); record(app,'B',location='South campus accounts office')
    record(app,'C',description='The library roof leaks during rainfall and has damaged the reading room furniture and books.')
    record(app,'D',location='')
    headers=login(client,'officer.rb@onecase.demo'); assert scan(client,headers) == []
    with app.app_context():
        assert process(a,1,DeterministicModels()) == 'completed'
        # Same-category cases with unrelated facts may have a low scoring record, never an alert.
        assert not db.session.scalar(select(Pair.id).where(Pair.band!='low'))
        assert not db.session.scalar(select(Notification.id).where(Notification.kind=='overlap'))


def test_resolved_predecessor_is_repeat_alert_with_timeline_not_overlap_and_no_scope_leak(app,client):
    old=record(app,'OLD',status='disposed',received=now()-timedelta(days=8))
    with app.app_context():
        closure=event(db.session.get(Complaint,old),'status_changed','Earlier issue resolved',
                      changes={'status':{'before':'under_review','after':'disposed'}},actor=False)
        closure.created_at=now()-timedelta(days=5); db.session.commit()
    new=record(app,'NEW')
    headers=login(client,'officer.rb@onecase.demo'); assert scan(client,headers) == []
    detail=client.get(f'/api/complaints/{new}').json
    recurrence=detail['recurrences'][0]
    assert recurrence['previous_case_id']==old and recurrence['resolved_at']<recurrence['new_received_at']
    notes = [n for n in client.get('/api/notifications').json['items'] if n['kind']=='repeat_issue']
    assert len(notes)==1 and 'TEST-OVERLAP-OLD' in notes[0]['message'] and 'resolved' in notes[0]['message'] and 'IST' in notes[0]['message']
    scan(client,headers)
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(CaseRecurrence))==1
        assert not db.session.scalar(select(Pair.id).where((Pair.case_a_id==old)|(Pair.case_b_id==old)))
        assert process(new,1,DeterministicModels())=='completed'
        assert db.session.scalar(select(func.count()).select_from(CaseRecurrence))==1
        assert not db.session.scalar(select(Pair.id).where((Pair.case_a_id==old)|(Pair.case_b_id==old)))
    with app.app_context():
        previous=db.session.get(Complaint,old)
        different_owner=db.session.scalar(select(User).where(User.email=='officer.pgrc@onecase.demo'))
        previous.bureau_id,previous.owner_id=different_owner.bureau_id,different_owner.id
        db.session.commit()
    assert client.get(f'/api/complaints/{new}').json['recurrences']==[]
    note=next(n for n in client.get('/api/notifications').json['items'] if n['kind']=='repeat_issue')
    assert 'TEST-OVERLAP-OLD' not in note['message']


def test_pdf_export_uses_filters_and_permissions(app,client,tmp_path):
    from pypdf import PdfReader
    import io
    login(client)
    response=client.get('/api/reports/complaints.pdf?category=Faculty')
    assert response.status_code==200 and response.mimetype=='application/pdf' and response.data.startswith(b'%PDF-')
    text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages)
    assert 'Faculty' in text and 'OC-' in text and 'Fee refund' not in text
    (tmp_path/'register.pdf').write_bytes(response.data)
    login(client,'auditor@onecase.demo')
    assert client.get('/api/reports/complaints.pdf').status_code==403


def test_pdf_does_not_promote_metadata_export_to_private_case_content(app,client):
    from app.models import Grant, PermissionGrant
    from pypdf import PdfReader
    import io
    with app.app_context():
        user=db.session.scalar(select(User).where(User.email=='auditor@onecase.demo'))
        grant=db.session.scalar(select(Grant).where(Grant.user_id==user.id,Grant.complaint_id==1))
        grant.fields=['basic']
        case=db.session.get(Complaint,1); case.issue_summary='Private summary must not appear in a metadata export'
        case.incident_location='Private annex room must not appear'
        db.session.add(PermissionGrant(user_id=user.id,complaint_id=1,operation='case.export',approval_reference='TEST-EXPORT',reason='Metadata export only'))
        db.session.commit()
    login(client,'auditor@onecase.demo')
    response=client.get('/api/reports/complaints.pdf')
    assert response.status_code==200
    text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages)
    assert 'Private summary' not in text and 'Private annex' not in text and 'details restricted' in text


def test_transitive_merge_cannot_override_an_existing_unrelated_decision(app,client):
    a=record(app,'A'); record(app,'B')
    headers=login(client,'officer.rb@onecase.demo'); pairs=scan(client,headers)
    assert client.post('/api/overlaps/bulk',headers=headers,json=payload(pairs,'reject')).status_code==200
    record(app,'C'); fresh=scan(client,headers)
    assert len(fresh)==2
    result=client.post('/api/overlaps/bulk',headers=headers,json=payload(fresh,'merge',primary_complaint_id=a))
    assert result.status_code==409
    with app.app_context():
        assert not db.session.scalar(select(CoordinationMember.complaint_id))


def test_priority_edit_does_not_realert_or_reset_unchanged_overlap_decisions(app,client):
    a=record(app,'A'); record(app,'B')
    headers=login(client,'officer.rb@onecase.demo'); pairs=scan(client,headers)
    assert client.post('/api/overlaps/bulk',headers=headers,json=payload(pairs,'reject')).status_code==200
    before=client.get(f'/api/complaints/{a}').json
    changed=client.patch(f'/api/complaints/{a}',headers=headers,json={'version':before['version'],
        'description':before['description'],'incident_location':before['incident_location'],
        'priority':'high','reason':'Priority revised without changing the complaint facts.'})
    assert changed.status_code==200 and changed.json['content_revision']==before['content_revision']
    assert scan(client,headers)==[]
