"""Expiring recovery links; raw tokens never enter the database or API responses."""
import re
import secrets
from datetime import timedelta, timezone
from threading import Thread
from flask import Blueprint, abort, current_app, make_response
from pydantic import Field
from sqlalchemy import select, update, delete
from .api import Input, parse, hasher, event
from .auth import digest
from .models import db, now, User, Session, PasswordReset
from .security import compromised_password, verify_mfa
from . import mail

password_reset_api = Blueprint("password_reset", __name__)
GENERIC_MESSAGE = "If an active account uses that email, you will receive a password reset link shortly."


class ForgotPassword(Input):
    email: str = Field(min_length=5, max_length=180)


class ResetPassword(Input):
    token: str = Field(min_length=40, max_length=128)
    password: str = Field(min_length=12, max_length=1024)
    confirm_password: str = Field(min_length=12, max_length=1024)
    verification_code: str = Field(default="", max_length=100)


def issue_token(user):
    token = secrets.token_urlsafe(48)
    db.session.add(PasswordReset(id=digest(token), user_id=user.id, expires_at=now() + timedelta(minutes=20)))
    return token


def deliver_reset(app, email):
    with app.app_context():
        token_id = None
        try:
            user = db.session.scalar(select(User).where(User.email == email, User.active.is_(True)))
            if not user:
                return
            token = issue_token(user)
            token_id = digest(token)
            link = mail.reset_url(token)
            recipient = user.email
            event(None, "password_reset_requested", "Password reset link requested", actor=user)
            db.session.commit()
            mail.send_email(recipient, "Reset your OneCase password",
                            "A password reset was requested for your OneCase account.\n\n"
                            + link + "\n\nThis link expires in 20 minutes and can be used once. "
                            "If you did not request this, you can ignore this email. Your password has not changed.")
        except Exception as error:
            db.session.rollback()
            if token_id:
                db.session.execute(delete(PasswordReset).where(PasswordReset.id == token_id))
                db.session.commit()
            app.logger.error("Password reset delivery failed (%s, status %s)", type(error).__name__, getattr(error, "code", "unavailable"))


def dispatch_reset(email):
    # Email delivery runs outside the request so its latency does not reveal accounts.
    Thread(target=deliver_reset, args=(current_app._get_current_object(), email), daemon=True).start()


def notify_changed(app, recipient):
    with app.app_context():
        try:
            mail.send_email(recipient, "Your OneCase password was changed",
                            "Your OneCase password was reset and all previous sessions were signed out. "
                            "If you did not make this change, contact your administrator immediately.")
        except Exception as error:
            app.logger.error("Password reset notification failed (%s)", type(error).__name__)


@password_reset_api.post("/auth/forgot-password")
def forgot_password():
    data = parse(ForgotPassword)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data.email):
        abort(422, description="Enter a valid email address.")
    if not mail.configured():
        abort(503, description="Password reset emails are not configured yet. Please try again after email setup is complete.")
    try:
        mail.reset_url("configuration-check")
    except ValueError:
        abort(503, description="Password reset email setup is incomplete. Please try again later.")
    dispatch_reset(data.email.lower())
    return {"message": GENERIC_MESSAGE}, 202


@password_reset_api.post("/auth/reset-password")
def reset_password():
    data = parse(ResetPassword)
    if data.password != data.confirm_password:
        abort(422, description="Passwords do not match.")
    if compromised_password(data.password):
        abort(422, description="Choose a password that is not on the compromised-password denylist.")
    reset = db.session.get(PasswordReset, digest(data.token))
    moment = now()
    if not reset or reset.used_at or reset.expires_at.replace(tzinfo=timezone.utc) <= moment:
        abort(422, description="This password reset link is invalid or expired. Request a new link.")
    user = db.session.scalar(select(User).where(User.id == reset.user_id, User.active.is_(True)).with_for_update())
    if not user:
        abort(422, description="This password reset link is invalid or expired. Request a new link.")
    if user.mfa_enabled and not verify_mfa(user, data.verification_code):
        return {"error": {"message": "Enter a valid authenticator or recovery code to reset your password.", "status": 403, "mfa_required": True}}, 403
    password_hash = hasher.hash(data.password)
    claimed = db.session.execute(update(PasswordReset).where(PasswordReset.id == reset.id,
                                  PasswordReset.used_at.is_(None), PasswordReset.expires_at > moment)
                                  .values(used_at=moment).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        abort(422, description="This password reset link is invalid or expired. Request a new link.")
    user.password_hash = password_hash
    recipient = user.email
    db.session.execute(delete(Session).where(Session.user_id == user.id))
    db.session.execute(update(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)).values(used_at=moment))
    event(None, "password_reset_completed", "Password reset completed; all sessions and reset links revoked", actor=user)
    db.session.commit()
    if mail.configured():
        Thread(target=notify_changed, args=(current_app._get_current_object(), recipient), daemon=True).start()
    response = make_response({"message": "Password updated. Sign in with your new password."})
    response.delete_cookie("onecase_session", secure=current_app.config["COOKIE_SECURE"], httponly=True, samesite="Strict")
    return response
