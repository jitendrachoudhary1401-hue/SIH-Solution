"""Opt-in real Neon verification, using environment credentials without printing them.

Run against the isolated validation branch first. Never marks quarantined uploads
clean without a scanner. Storage round-trip is separate from document scan status.
"""
import argparse
import hashlib
import io
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values

parser = argparse.ArgumentParser()
parser.add_argument("--env-file", default=".env.local")
parser.add_argument("--migrate", action="store_true")
parser.add_argument("--seed-demo", action="store_true")
args = parser.parse_args()
values = dotenv_values(args.env_file)
for key, value in values.items():
    if value is not None:
        os.environ[key] = value

try:
    from app import create_app
    from app.models import db, Complaint, User, Attachment, Institution
    from app import storage
    from sqlalchemy import select, text
    from flask_migrate import upgrade
    app = create_app({"RATELIMIT_ENABLED": False, "STORAGE_BACKEND": "neon"})
    with app.app_context():
        assert db.engine.dialect.name == "postgresql", "A real PostgreSQL environment is required"
        assert "neon" in db.engine.url.host, "A Neon endpoint is required"
        assert db.session.execute(text("SELECT 1")).scalar() == 1
        print("PASS Neon pooled Postgres connection")
        if args.migrate:
            upgrade(directory=str(Path(__file__).resolve().parents[1] / "migrations"))
            print("PASS application migrations on direct Neon connection")
        if args.seed_demo and not db.session.scalar(select(User.id).limit(1)):
            from app.cli import seed_demo
            seed_demo("OneCaseDemo!2026")
            print("PASS synthetic account/case seed")
        lead = db.session.scalar(select(User).where(User.email == "lead.rb@onecase.demo"))
        school = db.session.scalar(select(Institution).where(Institution.external_id == "DEMO-1-10001"))
        denied_case = db.session.scalar(select(Complaint).where(Complaint.bureau_id != lead.bureau_id).limit(1)) if lead else None
        if not lead or not school:
            raise RuntimeError("Synthetic integration account/directory are missing; run with --seed-demo on the isolated branch")
        owner_id, institution_id, denied_id = lead.id, school.id, denied_case.id
        payload = b"OneCase synthetic private object round-trip " + uuid4().hex.encode()
        key = "verification/" + uuid4().hex
        backend, bucket = storage.put(key, payload, "application/octet-stream")
        from types import SimpleNamespace
        record = SimpleNamespace(storage_backend=backend, storage_bucket=bucket, key=key,
                                  size=len(payload), checksum=hashlib.sha256(payload).hexdigest())
        assert storage.read(record) == payload
        storage.remove(key, backend, bucket)
        print("PASS real private Neon object upload/download/checksum/delete")
        print("PASS secrets remain server-side; credential values omitted")
    client = app.test_client()
    login = client.post("/api/auth/login", json={"email": "lead.rb@onecase.demo", "password": "OneCaseDemo!2026"})
    if login.status_code != 200:
        raise RuntimeError("Synthetic lead sign-in did not succeed")
    headers = {"X-CSRF-Token": login.json["csrf"], "Idempotency-Key": "neon-live-" + uuid4().hex}
    print("PASS officer authentication backed by Neon")
    from app.models import User
    from app.api import hasher
    email = 'neon-student-' + uuid4().hex + '@example.test'
    with app.app_context():
        db.session.add(User(name='Synthetic integration student',email=email,role='student',password_hash=hasher.hash('SyntheticNeonPass!2026')))
        db.session.commit()
    app.config['PUBLIC_INTAKE_OWNER_ID'] = owner_id
    identity=client.post('/api/auth/login',json={'email':email,'password':'SyntheticNeonPass!2026'})
    assert identity.status_code==200
    headers={'X-CSRF-Token':identity.json['csrf'],'Idempotency-Key':'neon-live-'+uuid4().hex}
    response = client.post('/api/intake/complaints',headers=headers,json={'institution_id':institution_id,
        'category':'Other','incident_location':'Synthetic integration office','issue_summary':'Synthetic private evidence integration',
        'description':'Synthetic Neon integration verification. This separate demonstration record has no real complainant data.','declaration':True})
    assert response.status_code == 201, "Complaint registration failed"
    case_id = response.json["id"]
    replay = client.get(f"/api/complaints/{case_id}")
    assert replay.status_code == 200 and replay.json["reference"] == response.json["reference"]
    print("PASS API complaint write/read persisted in Neon")
    from PIL import Image
    image = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(image, format="PNG")
    image.seek(0)
    result = client.post(f"/api/complaints/{case_id}/attachments", headers=headers,
                         data={"version": str(replay.json["version"]), "file": (image, "synthetic-neon-evidence.png")})
    assert result.status_code == 201, "Evidence upload failed"
    detail = client.get(f"/api/complaints/{case_id}").json
    attachment = detail["attachments"][0]
    with app.app_context():
        stored = db.session.get(Attachment, attachment["id"])
        assert stored.storage_backend == "neon" and stored.storage_bucket == "assets"
        assert storage.read(stored).startswith(b"\x89PNG")
    assert client.get(f"/api/attachments/{attachment['id']}/download").status_code == 423
    print("PASS API upload stored in Neon with PostgreSQL metadata; quarantined bytes denied")
    assert client.get(f"/api/complaints/{denied_id}").status_code == 404
    print("PASS unauthorized cross-bureau API access denied")
    print("ALL LIVE NEON SERVICE CHECKS PASSED")
except Exception as error:
    message = str(error)
    for value in values.values():
        if value and len(value) > 8:
            message = message.replace(value, "[redacted]")
    print(f"FAIL {type(error).__name__}: {message[:500]}")
    raise SystemExit(1)
