"""Quarantine pipeline. A missing scanner never produces a clean document."""
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from flask import current_app
from sqlalchemy import select
from botocore.exceptions import BotoCoreError, ClientError
from .models import db, Attachment, now, Complaint


def validate_file(path, media_type):
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "validate_evidence.py"), str(path), media_type]
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
    result = subprocess.run(command, capture_output=True, text=True, timeout=8, env=environment,
                            cwd=str(path.parent), creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise ValueError("Document parser rejected the file")


def scan_file(path):
    host = current_app.config.get("CLAMAV_HOST")
    if not host:
        return "pending", "Malware scanner unavailable. Evidence remains quarantined."
    with socket.create_connection((host, current_app.config["CLAMAV_PORT"]), timeout=5) as connection:
        connection.settimeout(8)
        connection.sendall(b"zINSTREAM\0")
        with path.open("rb") as content:
            while chunk := content.read(65536):
                connection.sendall(struct.pack("!I", len(chunk)) + chunk)
        connection.sendall(struct.pack("!I", 0))
        result = b""
        while b"\0" not in result and len(result) < 4096:
            chunk = connection.recv(4096 - len(result))
            if not chunk:
                break
            result += chunk
    if b"\0" not in result:
        return "pending", "Scanner did not confirm a complete result."
    result = result.split(b"\0", 1)[0]
    if result.endswith(b" FOUND"):
        return "rejected", "Malware check rejected this evidence."
    if result == b"stream: OK":
        return "clean", "Parser and malware checks completed."
    return "pending", "Scanner did not confirm a clean result."


def scan_pending(limit=10):
    from .api import event
    attachments = db.session.scalars(select(Attachment).where(Attachment.scan_state == "pending").order_by(Attachment.scan_checked_at.asc().nullsfirst(), Attachment.id).limit(limit)).all()
    for item in attachments:
        try:
            from .storage import read
            with tempfile.TemporaryDirectory(prefix="onecase-quarantine-") as temp:
                path = Path(temp) / item.key
                path.write_bytes(read(item))
                validate_file(path, item.media_type)
                state, detail = scan_file(path)
        except ValueError:
            state, detail = "rejected", "Document validation failed. Original evidence is quarantined."
        except (OSError, subprocess.TimeoutExpired, BotoCoreError, ClientError, RuntimeError):
            state, detail = "pending", "Validation/scanner unavailable or exceeded limits. Evidence remains quarantined."
        item.scan_state, item.scan_detail, item.scan_checked_at = state, detail, now()
        if state != "pending":
            case = db.session.get(Complaint, item.complaint_id)
            event(case, "evidence_scan", f"Evidence scan outcome: {state}", changes={"attachment_id": item.id, "state": state}, actor=False)
        db.session.commit()
