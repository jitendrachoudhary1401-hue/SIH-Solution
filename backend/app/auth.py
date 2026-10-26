"""Backend authorization: live role grants, object scope, appointments and conflicts."""
import hashlib
from functools import wraps
from flask import abort, g, request
from sqlalchemy import and_, or_, select
from .models import (db, Complaint, Grant, Session, now, RoleAssignment, PermissionGrant,
                     Appointment, Proceeding, CaseConflict)

ROLES = {"officer", "lead", "reviewer", "committee", "verifier", "executive", "auditor", "admin"}
OPERATIONS = {"case.read", "case.transition", "case.transfer", "case.route", "case.packet", "documents.read",
              "case.export", "audit.read", "monitor.aggregate", "case.proceeding", "case.compliance"}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def live(model):
    return and_(model.valid_from <= now(), or_(model.expires_at.is_(None), model.expires_at > now()), model.revoked_at.is_(None))


def roles(user=None):
    user = user or g.user
    assigned = set(db.session.scalars(select(RoleAssignment.role).where(RoleAssignment.user_id == user.id, live(RoleAssignment))))
    return ({user.role} | assigned) & ROLES


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


def permission_scope(operation, user=None):
    user = user or g.user
    grants = select(PermissionGrant).where(PermissionGrant.user_id == user.id, PermissionGrant.operation == operation, live(PermissionGrant))
    conditions = []
    for grant in db.session.scalars(grants):
        fields = []
        if grant.complaint_id is not None:
            fields.append(Complaint.id == grant.complaint_id)
        if grant.bureau_id is not None:
            fields.append(Complaint.bureau_id == grant.bureau_id)
        if grant.institution_id is not None:
            fields.append(Complaint.institution_id == grant.institution_id)
        if grant.region:
            from .models import Institution
            fields.append(Complaint.institution_id.in_(select(Institution.id).where(Institution.region == grant.region)))
        if fields:  # Empty grants never create system-wide content access.
            conditions.append(and_(*fields))
    return or_(*conditions) if conditions else Complaint.id == -1


def active_appointments(user=None):
    user = user or g.user
    return select(Appointment).where(Appointment.user_id == user.id, Appointment.valid_from <= now(), Appointment.expires_at > now(), Appointment.recused_at.is_(None))


def scope(user=None, aggregate=False):
    user = user or g.user
    effective = roles(user)
    grants = select(Grant.complaint_id).where(Grant.user_id == user.id, live(Grant))
    proceedings = select(Proceeding.complaint_id).where(Proceeding.id.in_(active_appointments(user).with_only_columns(Appointment.proceeding_id)))
    bureau = Complaint.bureau_id == user.bureau_id if effective & {"officer", "lead"} and user.bureau_id else Complaint.id == -1
    conflict = select(CaseConflict.complaint_id).where(CaseConflict.user_id == user.id, CaseConflict.resolved_at.is_(None))
    conditions = [bureau, Complaint.id.in_(grants), permission_scope("case.read", user)]
    if "committee" in effective:
        conditions.append(Complaint.id.in_(proceedings))
    if aggregate and "executive" in effective:
        conditions.append(permission_scope("monitor.aggregate", user))
    return and_(or_(*conditions), Complaint.id.not_in(conflict))


def has_permission(case, operation, user=None):
    user = user or g.user
    return bool(db.session.scalar(select(Complaint.id).where(Complaint.id == case.id, permission_scope(operation, user))))


def has_content(case, user=None):
    user = user or g.user
    if roles(user) & {"officer", "lead"} and case.bureau_id == user.bureau_id:
        return True
    grant = db.session.scalar(select(Grant).where(Grant.user_id == user.id, Grant.complaint_id == case.id, live(Grant)))
    return bool(grant and "content" in grant.fields or has_permission(case, "case.read", user))


def allowed(case, operation, user=None):
    user = user or g.user
    effective = roles(user)
    if not effective or not db.session.scalar(select(Complaint.id).where(Complaint.id == case.id, scope(user))):
        return False
    owner = "officer" in effective and case.owner_id == user.id
    lead = "lead" in effective and case.bureau_id == user.bureau_id
    if operation in ("case.edit", "case.action"):
        return owner or lead
    if operation == "case.transfer":
        return lead or ("officer" in effective and has_permission(case, operation, user))
    if operation in ("case.route", "case.packet", "case.proceeding", "case.compliance"):
        return lead or ("officer" in effective and has_permission(case, operation, user))
    if operation == "case.transition":
        return bool(effective & {"officer", "lead", "verifier"}) and has_permission(case, operation, user)
    if operation == "case.export":
        return bool(effective & {"officer", "lead", "auditor", "executive"}) and has_permission(case, operation, user)
    if operation == "documents.read":
        return owner or lead or has_permission(case, operation, user)
    if operation == "audit.read":
        return "auditor" in effective or has_permission(case, operation, user)
    return False


def case_or_404(case_id, write=False, lead=False, operation=None):
    case = db.session.scalar(select(Complaint).where(Complaint.id == case_id, scope()))
    if not case:
        abort(404, description="Case unavailable in your authorized scope.")
    operation = operation or ("case.transfer" if lead else "case.edit" if write else None)
    if operation and not allowed(case, operation):
        abort(403, description="Your current role and grants do not permit this case action.")
    return case


def proceeding_allowed(proceeding, operation="read", user=None):
    user = user or g.user
    case = db.session.get(Complaint, proceeding.complaint_id)
    if not db.session.scalar(select(Complaint.id).where(Complaint.id == case.id, scope(user))):
        return False
    if allowed(case, "case.proceeding", user) and operation in ("read", "coordinate", "import", "packet"):
        return True
    if "committee" not in roles(user):
        return has_content(case, user) if operation == "read" else False
    appointments = db.session.scalars(active_appointments(user).where(Appointment.proceeding_id == proceeding.id)).all()
    return any(operation == "read" or operation in a.permissions for a in appointments)


def document_allowed(case, attachment, user=None):
    user = user or g.user
    if allowed(case, "documents.read", user):
        return attachment.sensitivity == "standard" or has_permission(case, "documents.read", user)
    if attachment.proceeding_id:
        proceeding = db.session.get(Proceeding, attachment.proceeding_id)
        return bool(proceeding and proceeding_allowed(proceeding, "documents", user) and attachment.sensitivity == "standard")
    return False


def capabilities(user):
    effective = roles(user)
    return {"register": bool(effective & {"officer", "lead"}) and bool(user.bureau_id),
            "dashboard": bool(effective & {"officer", "lead", "reviewer", "verifier", "executive", "auditor"}),
            "cases": bool(effective - {"admin"}), "institutions": bool(effective - {"admin", "committee"}),
            "overlaps": "reviewer" in effective, "alerts": bool(effective - {"admin"}),
            "audit": bool(effective - {"admin", "executive"}), "reports": bool(effective & {"officer", "lead", "executive", "auditor"}),
            "admin": "admin" in effective}


def require_admin():
    if "admin" not in roles():
        abort(403, description="An authorized system administrator is required.")


def check_version(case, value):
    if value != case.version:
        abort(409, description="This record changed. Refresh and review the latest version before resubmitting.")
