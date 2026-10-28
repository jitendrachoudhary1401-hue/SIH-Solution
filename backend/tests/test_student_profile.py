from sqlalchemy import select
from app.models import db, User
from conftest import login
from test_registration import payload
from test_public_intake import details
from app.demo import seed_public_demo_accounts


def test_profile_validation_and_directory_privacy(app, client):
    for changes in ({'faculty_name':''}, {'admission_year':None}, {'passout_year':2020}, {'admission_year':1800}):
        assert client.post('/api/auth/register',json={**payload(), **changes}).status_code == 422
    assert client.post('/api/auth/register',json=payload()).status_code == 201
    response=client.post('/api/auth/login',json={'email':payload()['email'],'password':payload()['password']})
    assert response.json['user']['faculty_name'] == 'Dr. Example Faculty'
    assert client.get('/api/auth/me').json['user']['passout_year'] == 2030
    officer=app.test_client();login(officer)
    assert all('admission_year' not in u and 'faculty_name' not in u for u in officer.get('/api/directory').json['participants'])


def test_demo_student_routes_to_only_appointed_demo_faculty(app, client):
    with app.app_context():
        seed_public_demo_accounts()
    app.config['DEMO_ACCOUNTS_ENABLED']=True
    signed=client.post('/api/auth/demo-login',json={'role':'student'})
    assert signed.json['user']['faculty_name']=='Demo Faculty'
    headers={'X-CSRF-Token':signed.json['csrf'],'Idempotency-Key':'demo-student-workflow-001'}
    school=client.get('/api/intake/options').json['institutions'][0]
    assert client.post('/api/intake/complaints',headers=headers,json={**details(),'institution_id':1}).status_code==422
    response=client.post('/api/intake/complaints',headers=headers,json={**details(),'institution_id':school['id']})
    assert response.status_code==201
    cid=response.json['id']
    flow=client.get(f'/api/complaints/{cid}/case-workflow').json
    assert next(t for t in flow['team'] if t['role']=='faculty_reviewer')['name']=='Demo Faculty'
    faculty=app.test_client();signed=faculty.post('/api/auth/demo-login',json={'role':'faculty'})
    assert faculty.get('/api/complaints/1').status_code==404
    flow=faculty.get(f'/api/complaints/{cid}/case-workflow').json
    assert flow['can_report'] and flow['can_advance']
    moved=faculty.post(f'/api/complaints/{cid}/case-workflow/advance',headers={'X-CSRF-Token':signed.json['csrf']},
                      json={'version':flow['version'],'report':'Faculty claims this is resolved or false; the officer must independently review this initial recommendation.'})
    assert moved.status_code==200 and moved.json['stage']=='officer_triage'
    assert client.get(f'/api/complaints/{cid}').json['status']=='under_review'
