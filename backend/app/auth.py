import hashlib
from functools import wraps
from datetime import timedelta
from flask import abort, g, request
from sqlalchemy import or_, select
from .models import db, Complaint, Grant, Session, now


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def authenticated(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        token = request.cookies.get("onecase_session", "")
        session = db.session.get(Session, digest(token)) if token else None
        if not session or session.expires_at.replace(tzinfo=now().tzinfo) <= now() or not session.user.active:
            abort(401, description="Your session has expired. Please sign in.")
        g.user, g.session = session.user, session
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            import hmac
            if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), session.csrf):
                abort(403, description="Invalid request token. Refresh and try again.")
        return fn(*args, **kwargs)
    return wrapped


def scope(user=None):
    user = user or g.user
    # Reviewer, auditor and executive accounts still need explicit case grants.
    grants = select(Grant.complaint_id).where(Grant.user_id == user.id)
    bureau = Complaint.bureau_id == user.bureau_id if user.role in ("officer", "lead") else Complaint.id == -1
    return or_(bureau, Complaint.id.in_(grants))


def case_or_404(case_id, write=False, lead=False):
    case = db.session.scalar(select(Complaint).where(Complaint.id == case_id, scope()))
    if not case:
        abort(404, description="Case unavailable in your authorized scope.")
    if write and not (g.user.role == "lead" and case.bureau_id == g.user.bureau_id or
                      g.user.role == "officer" and case.owner_id == g.user.id):
        abort(403, description="Only the accountable officer or bureau lead can change this case.")
    if lead and not (g.user.role == "lead" and case.bureau_id == g.user.bureau_id):
        abort(403, description="A bureau lead must authorize this action.")
    return case


def check_version(case, value):
    if value != case.version:
        abort(409, description="This record changed. Refresh and review the latest version before resubmitting.")
