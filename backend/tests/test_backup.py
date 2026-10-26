import hashlib
import io
import sqlite3
from pathlib import Path
from conftest import login
from backup import backup, restore


def test_restore_case_history_and_private_attachment(app, client, tmp_path):
    headers = login(client)
    version = client.get("/api/complaints/1").json["version"]
    content = b"%PDF-1.4\nSynthetic restoration test"
    assert client.post("/api/complaints/1/attachments", headers=headers, data={"version": str(version), "file": (io.BytesIO(content), "restore.pdf")}).status_code == 201
    database = app.config["SQLALCHEMY_DATABASE_URI"].removeprefix("sqlite:///")
    archive = backup(database, app.config["STORAGE_PATH"], tmp_path / "backup.zip")
    restored = restore(archive, tmp_path / "restored")
    with sqlite3.connect(restored / "onecase.db") as connection:
        assert connection.execute("SELECT count(*) FROM complaint").fetchone()[0] == 8
        assert connection.execute("SELECT count(*) FROM action_event WHERE complaint_id=1").fetchone()[0] >= 2
        key, checksum = connection.execute("SELECT key, checksum FROM attachment").fetchone()
        assert hashlib.sha256((restored / "documents" / key).read_bytes()).hexdigest() == checksum
