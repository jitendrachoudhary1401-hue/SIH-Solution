import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import timedelta, timezone
from urllib.parse import quote
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, abort, current_app, g
from pydantic import Field
from .models import db, now, User, Session
from .auth import authenticated, digest, roles
from .api import Input, parse, hasher, event

security_api = Blueprint("security", __name__)


class Reauthentication(Input):
    password: str = Field(min_length=1, max_length=1024)
    verification_code: str = Field(default="", max_length=100)


class PasswordChange(Reauthentication):
    new_password: str = Field(min_length=12, max_length=1024)


class MFACode(Input):
    code: str = Field(min_length=6, max_length=20)


def cipher():
    key = current_app.config["MFA_ENCRYPTION_KEY"]
    if not key:
        abort(503, description="MFA encryption key is not configured. Contact the administrator.")
    return Fernet(key.encode())


def totp(secret, step):
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    result = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = result[-1] & 15
    return f"{(struct.unpack('>I', result[offset:offset + 4])[0] & 0x7fffffff) % 1000000:06d}"


def verify_mfa(user, code, pending=False):
    encrypted = user.mfa_pending_secret if pending else user.mfa_secret
    if not encrypted:
        return False
    try:
        secret = cipher().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return False
    step = int(time.time()) // 30
    for candidate in (step - 1, step, step + 1):
        if candidate > (user.last_totp_step or 0) and hmac.compare_digest(totp(secret, candidate), code.strip()):
            user.last_totp_step = candidate
            return True
    if not pending:
        hashed = digest(code.strip())
        if hashed in user.recovery_codes:
            user.recovery_codes = [c for c in user.recovery_codes if not hmac.compare_digest(c, hashed)]
            event(None, "mfa_recovery_used", "One-time MFA recovery code consumed", actor=user)
            return True
    return False


def verify_password(user, value):
    try:
        return hasher.verify(user.password_hash, value)
    except VerificationError:
        return False


def compromised_password(value):
    # Local denylist; no plaintext passwords or external queries leave the server.
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "security" / "compromised-password-sha256.txt"
    hashes = set(path.read_text(encoding="utf-8").splitlines()) if path.exists() else set()
    if not hashes:
        abort(503, description="Password denylist is unavailable. Account provisioning is temporarily disabled.")
    return digest(value.casefold()) in hashes


def require_recent_auth():
    moment = g.session.authenticated_at.replace(tzinfo=timezone.utc)
    if now() - moment > timedelta(minutes=current_app.config["STEP_UP_MINUTES"]):
        abort(403, description="Recent authentication required. Open Account security and confirm your password/MFA, then retry.")


@security_api.get("/auth/security")
@authenticated
def security_state():
    return {"mfa_enabled": g.user.mfa_enabled, "remaining_recovery_codes": len(g.user.recovery_codes),
            "recent_authentication": now() - g.session.authenticated_at.replace(tzinfo=timezone.utc) <= timedelta(minutes=current_app.config["STEP_UP_MINUTES"]),
            "idle_timeout_minutes": current_app.config["SESSION_IDLE_MINUTES"],
            "production_mfa_required": current_app.config["APP_ENV"] == "production" and bool(roles() & {"lead", "reviewer", "committee", "verifier", "admin"})}


@security_api.post("/auth/reauthenticate")
@authenticated
def reauthenticate():
    data = parse(Reauthentication)
    if not verify_password(g.user, data.password) or g.user.mfa_enabled and not verify_mfa(g.user, data.verification_code):
        abort(401, description="Authentication could not be verified.")
    g.session.authenticated_at = now()
    event(None, "reauthenticated", "Recent authentication verified")
    db.session.commit()
    return {"ok": True}


@security_api.post("/auth/mfa/setup")
@authenticated
def setup_mfa():
    require_recent_auth()
    if g.user.mfa_enabled:
        abort(409, description="MFA is already enabled. Use the approved recovery process to replace a lost authenticator.")
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    g.user.mfa_pending_secret = cipher().encrypt(secret.encode()).decode()
    event(None, "mfa_setup_started", "MFA enrollment started")
    db.session.commit()
    return {"secret": secret, "uri": f"otpauth://totp/OneCase:{quote(g.user.email)}?secret={secret}&issuer=OneCase&algorithm=SHA1&digits=6&period=30"}


@security_api.post("/auth/mfa/confirm")
@authenticated
def confirm_mfa():
    require_recent_auth()
    data = parse(MFACode)
    if not verify_mfa(g.user, data.code, pending=True):
        abort(422, description="The authenticator code is invalid or expired.")
    codes = [secrets.token_hex(6) for _ in range(10)]
    g.user.mfa_secret, g.user.mfa_pending_secret, g.user.mfa_enabled = g.user.mfa_pending_secret, None, True
    g.user.recovery_codes = [digest(c) for c in codes]
    db.session.query(Session).filter(Session.user_id == g.user.id, Session.id != g.session.id).delete()
    event(None, "mfa_enabled", "MFA enabled and other sessions revoked")
    db.session.commit()
    return {"recovery_codes": codes, "message": "Store these one-time codes safely. They are displayed once."}


@security_api.post("/auth/password")
@authenticated
def change_password():
    require_recent_auth()
    data = parse(PasswordChange)
    if not verify_password(g.user, data.password) or g.user.mfa_enabled and not verify_mfa(g.user, data.verification_code):
        abort(401, description="Authentication could not be verified.")
    if compromised_password(data.new_password):
        abort(422, description="Choose a passphrase that is not on the approved compromised-password denylist.")
    g.user.password_hash = hasher.hash(data.new_password)
    db.session.query(Session).filter(Session.user_id == g.user.id).delete()
    event(None, "password_changed", "Password changed and all sessions revoked")
    db.session.commit()
    return {"ok": True, "sign_in_required": True}
