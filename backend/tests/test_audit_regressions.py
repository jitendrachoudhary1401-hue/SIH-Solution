"""Regression coverage for the security and operational audit, using synthetic data."""
import json
import pytest
import time
from datetime import timedelta
from unittest.mock import patch
from sqlalchemy import select
from botocore.exceptions import ClientError
from conftest import login
from test_matching import DeterministicModels
from app.models import (db, now, User, Complaint, Proceeding, Appointment, PermissionGrant,
                        Pair, Review, Attachment, Job, Milestone, Notification, Institution)
from app.matching import process


def appointment(app):
    with app.app_context():
        member = db.session.scalar(select(User).where(User.role == 'committee'))
        admin = db.session.scalar(select(User).where(User.role == 'admin'))
        p = Proceeding(complaint_id=1, kind='student_institution', external_authority='Audit test committee',
            authority_reference='SYNTHETIC-AUDIT', institution_type='degree', jurisdiction='Test',
            framework='Synthetic', framework_version='1', context={})
        db.session.add(p); db.session.flush()
        db.session.add(Appointment(user_id=member.id, proceeding_id=p.id, designation='Test member', capacity='member',
            permissions=['contribute','documents'], expires_at=now()+timedelta(hours=1),
            approval_reference='SYNTHETIC-AUDIT', approved_by=admin.id))
        db.session.commit()
        return p.id, member.id


def test_basic_appointment_cannot_recover_narratives_from_history_or_lists(app, client):
    appointment(app)
    headers = login(client)
    marker = 'SYNTHETIC-PRIVATE-MARKER complaint description with confidential details.'
    version = client.get('/api/complaints/1').json['version']
    assert client.patch('/api/complaints/1', headers=headers,
        json={'version':version,'reason':marker,'description':marker,'next_action':marker}).status_code == 200
    login(client, 'committee@onecase.demo')
    detail = client.get('/api/complaints/1').json
    assert detail['has_content'] is False and marker not in json.dumps(detail)
    for path in ('/api/complaints/1/actions', '/api/audit-logs', '/api/dashboard/summary', '/api/complaints'):
        response = client.get(path)
        assert response.status_code == 200
        assert marker not in json.dumps(response.json), path


def test_production_enrollment_is_restricted_then_rotates_session(app, client):
    app.config.update(APP_ENV='production', COOKIE_SECURE=True, FRONTEND_PROXY_SECRET='')
    response = client.post('/api/auth/login', base_url='https://localhost',
        json={'email':'lead.rb@onecase.demo','password':'TestPassword!2026'})
    assert response.status_code == 200 and response.json['user']['mfa_enrollment_required']
    assert 'Max-Age=600' in response.headers['Set-Cookie']
    old_cookie = client.get_cookie('onecase_session').value
    csrf = {'X-CSRF-Token':response.json['csrf']}
    for path in ('/api/complaints','/api/dashboard/summary','/api/admin/workspace'):
        assert client.get(path, base_url='https://localhost').status_code == 403
    assert client.post('/api/auth/mfa/setup', base_url='https://localhost',json={}).status_code == 403
    setup = client.post('/api/auth/mfa/setup', headers=csrf, base_url='https://localhost', json={})
    assert setup.status_code == 200
    from app.security import totp
    confirmed = client.post('/api/auth/mfa/confirm', headers=csrf, base_url='https://localhost',
        json={'code':totp(setup.json['secret'],int(time.time())//30)})
    assert confirmed.status_code == 200 and len(confirmed.json['recovery_codes']) == 10
    assert not confirmed.json['user']['mfa_enrollment_required']
    assert client.get_cookie('onecase_session').value != old_cookie
    assert confirmed.json['csrf'] != csrf['X-CSRF-Token']
    assert client.get('/api/dashboard/summary',base_url='https://localhost').status_code == 200
    other = app.test_client(); other.set_cookie('onecase_session',old_cookie)
    assert other.get('/api/auth/me',base_url='https://localhost').status_code == 401


def test_material_revision_invalidates_decision_before_and_after_rematching(app, client):
    with app.app_context():
        process(1,1,DeterministicModels())
        pair = db.session.scalar(select(Pair).where(Pair.case_a_id==1,Pair.case_b_id==2))
        pair_id = pair.id
    headers = login(client,'reviewer@onecase.demo')
    pair = client.get(f'/api/overlaps/{pair_id}').json
    assert client.post(f'/api/overlaps/{pair_id}/review',headers=headers,
        json={'version':pair['version'],'decision':'related','reason':'Synthetic original relationship decision'}).status_code==200
    headers=login(client)
    version=client.get('/api/complaints/1').json['version']
    assert client.patch('/api/complaints/1',headers=headers,json={'version':version,'reason':'Material change for audit',
        'description':'Different synthetic infrastructure issue requiring fresh human examination.'}).status_code==200
    login(client,'reviewer@onecase.demo')
    before=client.get(f'/api/overlaps/{pair_id}').json
    assert before['stale'] and before['state']=='pending'
    with app.app_context(): process(1,2,DeterministicModels())
    after=client.get(f'/api/overlaps/{pair_id}').json
    assert not after['stale'] and after['state']=='pending'
    with app.app_context():
        assert db.session.scalar(select(Review).where(Review.pair_id==pair_id)).revisions['1']==1


def test_aggregate_grant_returns_counts_without_case_or_history_payloads(app, client):
    with app.app_context():
        user=db.session.scalar(select(User).where(User.role=='executive'))
        admin=db.session.scalar(select(User).where(User.role=='admin'))
        db.session.add(PermissionGrant(user_id=user.id,operation='monitor.aggregate',bureau_id=1,
            expires_at=now()+timedelta(hours=1),approval_reference='SYNTHETIC-AUDIT',reason='Test aggregate only',approved_by=admin.id))
        db.session.commit()
        count=len(db.session.scalars(select(Complaint).where(Complaint.bureau_id==1)).all())
    login(client,'monitor@onecase.demo')
    dashboard=client.get('/api/dashboard/summary').json
    assert dashboard['total']==count and dashboard['attention']==[] and dashboard['recent']==[]
    assert client.get('/api/complaints').json['items']==[]
    assert client.get('/api/complaints/1').status_code==404


def test_storage_failure_stays_pending_and_scan_batch_does_not_starve(app):
    with app.app_context():
        for index in range(2):
            db.session.add(Attachment(complaint_id=1,filename=f'test-{index}.pdf',key=f'audit-{index}',media_type='application/pdf',
                size=12,checksum='0'*64,storage_backend='neon',storage_bucket='synthetic',scan_state='pending'))
        db.session.commit()
        from app.documents import scan_pending
        error=ClientError({'Error':{'Code':'NoSuchKey','Message':'Synthetic missing object'}},'GetObject')
        with patch('app.storage.read',side_effect=error):
            scan_pending(limit=1); scan_pending(limit=1)
        items=db.session.scalars(select(Attachment)).all()
        assert all(item.scan_checked_at and item.scan_state=='pending' for item in items)


def test_worker_continues_monitoring_after_a_stage_fails(app):
    import worker
    with app.app_context(), patch('worker.tick',side_effect=RuntimeError('synthetic')) as tick, \
            patch('worker.monitor') as monitor, patch('worker.scan_pending') as scan:
        assert worker.run_cycle() is False
        tick.assert_called_once(); monitor.assert_called_once(); scan.assert_called_once()


def test_completed_matching_job_can_be_requeued(app,client):
    with app.app_context():
        process(1,1,DeterministicModels())
        db.session.get(Job,1).state='completed'; db.session.commit()
    headers=login(client)
    version=client.get('/api/complaints/1').json['version']
    assert client.post('/api/complaints/1/matching/retry',headers=headers,json={'version':version}).status_code==200
    with app.app_context(): assert db.session.get(Job,1).state=='queued'


def test_institution_review_preserves_string_id_and_requeues_failed_matching(app,client):
    with app.app_context():
        case=db.session.get(Complaint,8)
        job=db.session.scalar(select(Job).where(Job.complaint_id==case.id))
        job.state='failed'; db.session.commit()
        institution_id=case.institution_id
    headers=login(client,'admin@onecase.demo')
    response=client.post(f'/api/admin/institutions/{institution_id}/verify',headers=headers,
        json={'external_id':'0000123','approval_reference':'SYNTHETIC-VERIFICATION','reason':'Verified against authorized synthetic source'})
    assert response.status_code==200 and response.json['external_id']=='0000123'
    with app.app_context(): assert db.session.scalar(select(Job).where(Job.complaint_id==8)).state=='queued'
    forbidden=client.post(f'/api/admin/institutions/{institution_id}/verify',headers=headers,
        json={'external_id':'DIFFERENT-ID','approval_reference':'SYNTHETIC-VERIFICATION','reason':'An attempted silent identity change'})
    assert forbidden.status_code==409


def test_milestone_reminders_respect_scope_and_are_idempotent(app):
    proceeding_id,member_id=appointment(app)
    with app.app_context():
        milestone=Milestone(proceeding_id=proceeding_id,kind='report_due',title='Audit report due',start_at=now()-timedelta(days=2),
            due_at=now()-timedelta(hours=1),original_due_at=now()-timedelta(hours=1),recipient_id=member_id,
            policy_snapshot={'confirmed':True,'administrative':True})
        db.session.add(milestone); db.session.commit()
        from app.jobs import monitor
        monitor(); monitor()
        reminders=db.session.scalars(select(Notification).where(Notification.dedup_key.like(f'milestone:{milestone.id}:%'))).all()
        assert len(reminders)==1 and reminders[0].user_id==member_id
        assert db.session.get(Complaint,1).status!='disposed'
        db.session.get(Complaint,1).status='disposed'
        milestone.revision+=1
        db.session.commit()
        monitor()
        # Internal closure does not stop a separate unfinished proceeding clock.
        assert len(db.session.scalars(select(Notification).where(Notification.dedup_key.like(f'milestone:{milestone.id}:%'))).all())==2


def test_proxy_client_identity_requires_the_shared_secret(tmp_path,monkeypatch):
    from app import create_app
    monkeypatch.setenv('RATE_LIMIT_LOGIN','2 per minute')
    app=create_app({'TESTING':True,'APP_ENV':'development','RATELIMIT_ENABLED':True,
        'RATELIMIT_STORAGE_URI':'memory://','FRONTEND_PROXY_SECRET':'synthetic-proxy-secret-for-audit',
        'SQLALCHEMY_DATABASE_URI':'sqlite:///'+(tmp_path/'proxy.db').as_posix(),
        'STORAGE_PATH':str(tmp_path/'documents'),'STORAGE_BACKEND':'local'})
    with app.app_context(): db.create_all()
    client=app.test_client()
    for index in range(3):
        response=client.post('/api/auth/login',json={'email':f'auth{index}@example.test','password':'invalid'},
            headers={'X-OneCase-Proxy-Key':'synthetic-proxy-secret-for-audit','X-OneCase-Client-IP':f'198.51.100.{index+1}'},
            environ_overrides={'REMOTE_ADDR':'192.0.2.1'})
        assert response.status_code==401
    statuses=[]
    for index in range(3):
        response=client.post('/api/auth/login',json={'email':f'fake{index}@example.test','password':'invalid'},
            headers={'X-OneCase-Proxy-Key':'wrong-secret','X-OneCase-Client-IP':f'203.0.113.{index+1}','X-Forwarded-For':f'203.0.113.{index+1}'},
            environ_overrides={'REMOTE_ADDR':'192.0.2.2'})
        statuses.append(response.status_code)
    assert statuses==[401,401,429]


def test_timestamps_normalize_before_storage_and_receipt_filter_uses_ist(app,client):
    from datetime import datetime, timezone
    from app.api import Registration
    record=Registration(institution_id=1,owner_id=1,category='Other',description='Synthetic timezone boundary complaint.',
        received_at='2026-10-27T00:30:00+05:30',next_action='Review the synthetic timezone case')
    assert record.received_at==datetime(2026,10,26,19,0,tzinfo=timezone.utc)
    with app.app_context():
        case=db.session.get(Complaint,1); case.received_at=record.received_at; db.session.commit()
    login(client)
    same_day=client.get('/api/complaints?from=2026-10-27&to=2026-10-27').json['items']
    previous_day=client.get('/api/complaints?from=2026-10-26&to=2026-10-26').json['items']
    assert 1 in [c['id'] for c in same_day] and 1 not in [c['id'] for c in previous_day]


@pytest.mark.parametrize('changes,expected',[
    ({'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:'},'PostgreSQL'),
    ({'FRONTEND_PROXY_SECRET':''},'FRONTEND_PROXY_SECRET'),
    ({'STORAGE_BACKEND':'local'},'Neon evidence-storage'),
])
def test_production_rejects_unsafe_deployment_configuration(changes,expected):
    from app import create_app
    from cryptography.fernet import Fernet
    settings={'TESTING':True,'APP_ENV':'production','COOKIE_SECURE':True,'SECRET_KEY':'synthetic-secret-'*3,
        'MFA_ENCRYPTION_KEY':Fernet.generate_key().decode(),'FRONTEND_PROXY_SECRET':'synthetic-proxy-'*3,
        'SQLALCHEMY_DATABASE_URI':'postgresql+psycopg://unused:unused@localhost/unused',
        'STORAGE_BACKEND':'neon','AWS_ENDPOINT_URL_S3':'https://storage.example.test','AWS_REGION':'test',
        'AWS_ACCESS_KEY_ID':'synthetic','AWS_SECRET_ACCESS_KEY':'synthetic'}
    with pytest.raises(RuntimeError,match=expected): create_app({**settings,**changes})


def test_known_password_seed_cannot_run_in_production(app):
    import click
    from app.cli import seed_demo,configure_demo_access
    app.config['APP_ENV']='production'
    with app.app_context():
        for command in (lambda:seed_demo('OneCaseDemo!2026'),configure_demo_access):
            with pytest.raises(click.ClickException,match='disabled in production'): command()
