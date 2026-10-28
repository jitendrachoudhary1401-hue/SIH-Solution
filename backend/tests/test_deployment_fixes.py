import pytest
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import psycopg
from flask import g
from conftest import login
from app.models import db, Institution, PermissionGrant, User, Complaint, Pair, Notification
from app.demo import seed_public_demo_accounts
from app.api import filtered_cases
from test_public_intake import public_login, details
from test_overlap_actions import record, scan


def test_demo_setup_repairs_verification_and_scoped_export_without_touching_real_institutions(app,client):
    with app.app_context():
        seed_public_demo_accounts()
        demo=db.session.scalar(select(Institution).where(Institution.external_id=='ONECASE-PUBLIC-DEMO'))
        demo.verified=False; db.session.commit()
        seed_public_demo_accounts()
        assert db.session.get(Institution,demo.id).verified
        real=db.session.get(Institution,4)
        assert not real.verified
        grant_count=db.session.scalar(select(func.count()).select_from(PermissionGrant).where(PermissionGrant.approval_reference=='SYNTHETIC-DEMO-EXPORT'))
        assert grant_count==2
        seed_public_demo_accounts()
        assert db.session.scalar(select(func.count()).select_from(PermissionGrant).where(PermissionGrant.approval_reference=='SYNTHETIC-DEMO-EXPORT'))==2
    app.config['DEMO_ACCOUNTS_ENABLED']=True
    result=client.post('/api/auth/demo-login',json={'role':'officer'})
    assert result.json['user']['capabilities']['export_register']
    assert not result.json['user']['capabilities']['register']
    response=client.get('/api/reports/complaints.pdf')
    assert response.status_code==200 and response.data.startswith(b'%PDF-')
    # No real records are exposed through demo export/read scope.
    assert client.get('/api/complaints').json['total']==0


def test_numeric_filters_use_integer_postgres_binds_and_reject_bad_values(app,client):
    login(client)
    assert client.get('/api/overlaps?bureau=1').status_code==200
    assert client.get('/api/overlaps?bureau=invalid').status_code==422
    assert client.get('/api/complaints?institution=-1').status_code==422
    with app.test_request_context('/api/overlaps?bureau=1&institution=1'):
        g.user=db.session.scalar(select(User).where(User.email=='lead.rb@onecase.demo'))
        compiled=filtered_cases().compile(dialect=psycopg.dialect())
        assert all(str(bind.type)=='INTEGER' for key,bind in compiled.binds.items() if key.startswith(('bureau_id_','institution_id_')))


@pytest.mark.parametrize('role',['student','parent','faculty','staff','other'])
def test_only_submitter_roles_use_both_registration_routes(app,client,role):
    headers=public_login(client,role)
    assert client.get('/api/auth/me').json['user']['capabilities']['submit_complaint']
    assert client.post('/api/complaints',headers=headers,json=details()).status_code==201


@pytest.mark.parametrize('email',['officer.rb@onecase.demo','lead.rb@onecase.demo','reviewer@onecase.demo','committee@onecase.demo','verifier@onecase.demo','monitor@onecase.demo','auditor@onecase.demo','admin@onecase.demo'])
def test_review_roles_cannot_register_through_either_route(app,client,email):
    headers=login(client,email)
    for route in ('/api/complaints','/api/intake/complaints'):
        assert client.post(route,headers=headers,json=details()).status_code==403


def test_other_account_can_register_through_both_routes(app,client):
    from uuid import uuid4
    headers=public_login(client,'other')
    assert client.get('/api/auth/me').json['user']['capabilities']['submit_complaint']
    for route in ('/api/complaints','/api/intake/complaints'):
        response=client.post(route,headers={**headers,'Idempotency-Key':str(uuid4())},json=details())
        assert response.status_code==201 and response.json['is_submitter']
        assert response.json['handling_stage']=='initial_review'


def test_overlap_notification_links_pair_and_disappears_when_either_case_is_closed(app,client):
    a=record(app,'ACTIVE-A'); b=record(app,'ACTIVE-B')
    headers=login(client,'officer.rb@onecase.demo'); pairs=scan(client,headers)
    assert len(pairs)==1
    notes=[n for n in client.get('/api/notifications').json['items'] if n['kind']=='overlap']
    assert len(notes)==2 and all(n['action_url']==f'/overlaps/{pairs[0]["id"]}' for n in notes)
    assert client.get(notes[0]['action_url'].replace('/overlaps/','/api/overlaps/')).status_code==200
    with app.app_context():
        db.session.get(Complaint,b).status='disposed'; db.session.commit()
    assert client.get('/api/overlaps').json['total']==0
    assert not [n for n in client.get('/api/notifications').json['items'] if n['kind']=='overlap']
    assert client.get('/api/dashboard/summary').json['pending_pairs']==0
