from datetime import timedelta
from sqlalchemy import select, func
from app.models import db, User, Complaint, Grant, RoleAssignment, now
from app.demo import seed_public_demo_accounts, DEMO_ROLES


def test_demo_accounts_are_persistent_idempotent_and_start_empty(app, client):
    with app.app_context():
        before = db.session.scalar(select(func.count()).select_from(Complaint))
        admin_count = db.session.scalar(select(func.count()).select_from(User).where(User.role == "admin"))
        assert seed_public_demo_accounts() == len(DEMO_ROLES)
        assert seed_public_demo_accounts() == 0
        assert db.session.scalar(select(func.count()).select_from(Complaint)) == before
        assert db.session.scalar(select(func.count()).select_from(User).where(User.role == "admin")) == admin_count
    assert client.get('/api/auth/demo-accounts').json == {'enabled': False, 'accounts': []}
    assert client.post('/api/auth/demo-login', json={'role': 'student'}).status_code == 404
    app.config['DEMO_ACCOUNTS_ENABLED'] = True
    assert {row['role'] for row in client.get('/api/auth/demo-accounts').json['accounts']} == set(DEMO_ROLES)
    for role in DEMO_ROLES:
        response = client.post('/api/auth/demo-login', json={'role': role})
        assert response.status_code == 200
        assert response.json['user']['role'] == role and response.json['user']['is_demo'] is True
        assert response.json['user']['capabilities'].get('admin', False) is False
        assert client.get('/api/auth/me').json['user']['role'] == role
        assert client.get('/api/account/summary').json == {'total': 0, 'active': 0, 'closed': 0, 'unread_alerts': 0}
        headers = {'X-CSRF-Token': response.json['csrf']}
        assert client.post('/api/auth/password', json={}, headers=headers).status_code == 403
        assert client.post('/api/auth/logout', json={}, headers=headers).status_code == 200
    assert client.post('/api/auth/demo-login', json={'role': 'admin'}).status_code == 422


def test_demo_identity_cannot_read_real_cases_or_become_admin_even_with_grants(app, client):
    with app.app_context():
        seed_public_demo_accounts()
        demo = db.session.scalar(select(User).where(User.email == 'demo.lead@onecase.demo'))
        admin = db.session.scalar(select(User).where(User.role == 'admin'))
        db.session.add(Grant(user_id=demo.id, complaint_id=1))
        db.session.add(RoleAssignment(user_id=demo.id, role='admin', expires_at=now()+timedelta(hours=1), approved_by=admin.id, approval_reference='SYNTHETIC-TEST', reason='Verify public demo isolation'))
        db.session.commit()
    app.config['DEMO_ACCOUNTS_ENABLED'] = True
    response = client.post('/api/auth/demo-login', json={'role': 'lead'})
    assert response.status_code == 200 and 'admin' not in response.json['user']['roles']
    assert client.get('/api/complaints/1').status_code == 404
    assert client.get('/api/complaints').json['total'] == 0
    assert client.get('/api/admin/workspace').status_code == 403
    directory = client.get('/api/directory').json
    assert all(user['is_demo'] for user in directory['participants'])
    assert {b['code'] for b in directory['bureaus']} == {'PUBLIC-DEMO'}
    assert {item['external_id'] for item in client.get('/api/institutions').json['items']} == {'ONECASE-PUBLIC-DEMO'}
    assert client.get('/api/institutions/1').status_code == 404
