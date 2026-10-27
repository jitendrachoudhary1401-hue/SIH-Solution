import io
from uuid import uuid4
import pytest
from sqlalchemy import select
from pypdf import PdfReader
from conftest import login, approved_test_evidence
from test_registration import payload
from app.models import db, User, Complaint, ComplaintReport, Notification, Attachment


def public_login(client, role='student', email='intake@example.com'):
    assert client.post('/api/auth/register', json=payload(role, email)).status_code == 201
    result = client.post('/api/auth/login', json={'email': email, 'password': 'PersonalPassphrase!2026'})
    assert result.status_code == 200
    return {'X-CSRF-Token': result.json['csrf'], 'Idempotency-Key': str(uuid4())}


def details():
    return {'institution_name': 'Actual Technical College', 'region': 'Rajasthan', 'category': 'Fee refund',
            'issue_summary': 'Refund has not been paid', 'description': 'The institution has not refunded the fee after withdrawal. Please investigate.',
            'affected_person': 'Enrolled Student', 'representation_basis': 'Parent and guardian of the enrolled student', 'declaration': True}


@pytest.mark.parametrize('role', ['student', 'parent', 'faculty', 'staff', 'other'])
def test_intake_ownership_assignment_and_idempotency(app, client, role):
    with app.app_context():
        officer_id = db.session.scalar(select(User.id).where(User.email == 'officer.rb@onecase.demo'))
    app.config['PUBLIC_INTAKE_OWNER_ID'] = officer_id
    headers = public_login(client, role)
    data = details()
    response = client.post('/api/intake/complaints', json=data, headers=headers)
    assert response.status_code == 201, response.json
    case = response.json
    assert len(case['reference']) == 40 and case['owner_id'] == officer_id
    assert client.post('/api/intake/complaints', json=data, headers=headers).json['id'] == case['id']
    assert client.post('/api/intake/complaints', json={**data, 'description': 'A different description for an attempted duplicate.'}, headers=headers).status_code == 409
    assert client.post('/api/intake/complaints', json={**data, 'owner_id': officer_id}, headers={**headers, 'Idempotency-Key': str(uuid4())}).status_code == 422
    another = client.post('/api/intake/complaints', json=data, headers={**headers, 'Idempotency-Key': str(uuid4())})
    assert another.status_code == 201 and another.json['reference'] != case['reference']
    assert client.get('/api/account/summary').json['total'] == 2
    assert client.patch(f"/api/complaints/{case['id']}", headers=headers, json={'version': case['version'], 'reason': 'Unauthorized edit', 'priority': 'urgent'}).status_code == 403
    other = app.test_client()
    public_login(other, 'student', 'different@example.com')
    for suffix in ['', '/actions']:
        assert other.get(f"/api/complaints/{case['id']}{suffix}").status_code == 404
    assert other.get('/api/complaints').json['items'] == []
    actor = app.test_client()
    action_headers = login(actor, 'officer.rb@onecase.demo')
    assert actor.get(f"/api/complaints/{case['id']}").status_code == 200
    assert actor.post(f"/api/complaints/{case['id']}/actions", headers=action_headers, json={'version': case['version'], 'reason': 'Requested the fee refund records', 'next_action': 'Await the institution response'}).status_code == 200
    timeline = client.get(f"/api/complaints/{case['id']}/actions").json['items']
    assert timeline[0]['actor'] == 'Meera Iyer' and timeline[0]['created_at'] and timeline[0]['actor_id'] == officer_id
    unrelated = app.test_client()
    login(unrelated, 'officer.pgrc@onecase.demo')
    assert unrelated.get(f"/api/complaints/{case['id']}").status_code == 404
    if role == 'student':
        with app.app_context():
            owner = db.session.get(User, officer_id)
            db.session.add(User(name='Unassigned officer in the same bureau', email='unassigned@example.com',
                                password_hash=owner.password_hash, role='officer', bureau_id=owner.bureau_id))
            db.session.commit()
        login(unrelated, 'unassigned@example.com')
        assert unrelated.get(f"/api/complaints/{case['id']}").status_code == 404
    admin = app.test_client()
    login(admin, 'admin@onecase.demo')
    assert admin.get(f"/api/complaints/{case['id']}/actions").status_code == 200


def test_uploads_video_privacy_scanning_and_retry(app, client, tmp_path):
    import av
    from PIL import Image
    from app.documents import validate_file, scan_pending
    headers = public_login(client)
    case = client.post('/api/intake/complaints', json=details(), headers=headers).json
    stream = io.BytesIO()
    with av.open(stream, 'w', format='mp4') as container:
        video = container.add_stream('mpeg4', rate=24)
        video.width, video.height, video.pix_fmt = 64, 64, 'yuv420p'
        frame = av.VideoFrame(64, 64, 'yuv420p')
        for plane in frame.planes:
            plane.update(bytes(plane.buffer_size))
        for packet in video.encode(frame):
            container.mux(packet)
        for packet in video.encode():
            container.mux(packet)
    video_bytes = stream.getvalue()
    path = tmp_path / 'proof.mp4'
    path.write_bytes(video_bytes)
    validate_file(path, 'video/mp4')
    image = io.BytesIO(); Image.new('RGB', (30, 30), 'white').save(image, 'PNG')
    version = case['version']
    ids = []
    for name, content in [('proof.mp4', video_bytes), ('proof.png', image.getvalue())]:
        key = str(uuid4())
        def upload(value=content):
            return client.post(f"/api/complaints/{case['id']}/attachments", headers=headers,
                               data={'version': str(version), 'upload_key': key, 'file': (io.BytesIO(value), name)})
        response = upload()
        assert response.status_code == 201, response.json
        assert upload().status_code == 200
        assert upload(b'different').status_code == 409
        version = response.json['version']; ids.append(response.json['id'])
    assert client.get(f'/api/attachments/{ids[0]}/download').status_code == 423
    other = app.test_client(); public_login(other, email='outsider@example.com')
    assert other.get(f'/api/attachments/{ids[0]}/download').status_code == 404
    with app.app_context():
        app.config['CLAMAV_HOST'] = ''
        scan_pending()
        assert all(db.session.get(Attachment, i).scan_state == 'pending' for i in ids)
    assert client.get(f"/api/complaints/{case['id']}/actions").json['items'][0]['proof'][0]['id'] == ids[-1]
    path.write_bytes(b'\x00\x00\x00\x20ftypisom' + bytes(100))
    with pytest.raises(ValueError):
        validate_file(path, 'video/mp4')


def test_closure_pdf_watermark_frozen_history_and_authorization(app, client):
    with app.app_context():
        app.config['PUBLIC_INTAKE_OWNER_ID'] = db.session.scalar(select(User.id).where(User.email == 'officer.rb@onecase.demo'))
    headers = public_login(client)
    case = client.post('/api/intake/complaints', json=details(), headers=headers).json
    proof_id = approved_test_evidence(app, case['id'])
    actor = app.test_client(); auth = login(actor)
    current = actor.get(f"/api/complaints/{case['id']}").json
    recorded = actor.post(f"/api/complaints/{case['id']}/actions", headers=auth, json={'version': current['version'], 'reason': 'Reviewed the refund payment proof', 'evidence_ids': [proof_id]})
    assert recorded.status_code == 200
    response = actor.post(f"/api/complaints/{case['id']}/status", headers=auth,
                          json={'version': recorded.json['version'], 'status': 'disposed', 'reason': 'Refund payment verified and complaint resolved', 'outcome_document_id': proof_id, 'communication': 'Student notified through portal, REF-2026-001'})
    assert response.status_code == 200, response.json
    report_id = response.json['reports'][0]['id']
    path = f"/api/complaints/{case['id']}/reports/{report_id}.pdf"
    pdf = client.get(path)
    assert pdf.status_code == 200 and pdf.mimetype == 'application/pdf'
    text = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.data)).pages)
    for expected in [case['reference'], 'COMPLAINT RECORD', 'Aarav Sharma', 'Reviewed the refund payment proof', 'Student notified', 'SHA-256', 'UTC']:
        assert expected in text
    assert all('ONECASE' in page.extract_text() for page in PdfReader(io.BytesIO(pdf.data)).pages)
    admin = app.test_client(); login(admin, 'admin@onecase.demo')
    assert admin.get(path).data == pdf.data
    outsider = app.test_client(); public_login(outsider, email='outsider@example.com')
    assert outsider.get(path).status_code == 404
    assert client.post(f"/api/complaints/{case['id']}/attachments", headers=headers, data={'version': str(response.json['version']), 'file': (io.BytesIO(b'%PDF-'), 'late.pdf')}).status_code == 409
    reopen = actor.post(f"/api/complaints/{case['id']}/status", headers=auth, json={'version': response.json['version'], 'status': 'under_review', 'reason': 'Additional information requires a further review'})
    assert reopen.status_code == 200
    assert client.get(path).data == pdf.data
    with app.app_context():
        assert db.session.scalar(select(ComplaintReport).where(ComplaintReport.id == report_id)).checksum == pdf.headers['X-Content-SHA256']
        assert len(db.session.scalars(select(Notification).where(Notification.kind == 'closure_report', Notification.complaint_id == case['id'])).all()) == 2
    from pathlib import Path
    preview = Path(__file__).resolve().parents[2] / 'tmp' / 'pdfs'
    preview.mkdir(parents=True, exist_ok=True)
    (preview / 'synthetic-closure-preview.pdf').write_bytes(pdf.data)


def test_demo_intake_uses_only_the_demo_institution_and_officer(app, client):
    from app.demo import seed_public_demo_accounts
    with app.app_context():
        seed_public_demo_accounts()
    app.config['DEMO_ACCOUNTS_ENABLED'] = True
    signed = client.post('/api/auth/demo-login', json={'role': 'student'})
    assert signed.status_code == 200, signed.json
    headers = {'X-CSRF-Token': signed.json['csrf'], 'Idempotency-Key': str(uuid4())}
    options = client.get('/api/intake/options').json
    assert len(options['institutions']) == 1
    result = client.post('/api/intake/complaints', headers=headers, json={**details(), 'institution_id': options['institutions'][0]['id']})
    assert result.status_code == 201, result.json
    assert result.json['bureau'] == 'PUBLIC-DEMO'
    assert client.post('/api/intake/complaints', headers={**headers, 'Idempotency-Key': str(uuid4())}, json={**details(), 'institution_id': 1}).status_code == 422
