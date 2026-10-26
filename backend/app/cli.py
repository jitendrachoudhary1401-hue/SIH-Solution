import click
from sqlalchemy import select
from .models import db, now, Bureau, User, Institution, Grant


def register(app):
    @app.cli.command("init-system")
    def init_system():
        """Initialize official AICTE bureau configuration without creating business or demo records."""
        existing_rb = db.session.scalar(select(Bureau).where(Bureau.code == "RB"))
        existing_pgrc = db.session.scalar(select(Bureau).where(Bureau.code == "PGRC"))
        added = []
        if not existing_rb:
            rb = Bureau(code="RB", name="Regulation Bureau")
            db.session.add(rb)
            added.append("RB (Regulation Bureau)")
        if not existing_pgrc:
            pgrc = Bureau(code="PGRC", name="Public Grievance Redressal Cell")
            db.session.add(pgrc)
            added.append("PGRC (Public Grievance Redressal Cell)")
        if added:
            db.session.commit()
            click.echo(f"Initialized official bureaus: {', '.join(added)}.")
        else:
            click.echo("Official bureaus (RB, PGRC) are already initialized.")

    @app.cli.command("create-user")
    @click.option("--email", required=True, help="Officer / administrator email address")
    @click.option("--name", required=True, help="Full name of the officer")
    @click.option("--role", type=click.Choice(["officer", "lead", "reviewer", "auditor", "executive", "admin"]), required=True)
    @click.option("--bureau", type=str, help="Bureau code (e.g. RB or PGRC) for officers and leads")
    @click.password_option()
    def create_user(email, name, role, bureau, password):
        """Provision an authorized account through the administrative workflow."""
        from .api import hasher
        if len(password) < 12:
            raise click.ClickException("Password must have at least 12 characters.")
        bureau_record = None
        if role in ("officer", "lead"):
            if not bureau:
                raise click.ClickException("A valid bureau code (e.g. RB or PGRC) is required for officers and leads.")
            bureau_record = db.session.scalar(select(Bureau).where(Bureau.code == bureau.strip().upper()))
            if not bureau_record:
                raise click.ClickException(f"Bureau '{bureau}' not found. Run 'flask init-system' first.")
        existing = db.session.scalar(select(User).where(User.email == email.strip().lower()))
        if existing:
            raise click.ClickException(f"User with email '{email}' already exists.")
        user = User(
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=hasher.hash(password),
            role=role,
            bureau_id=bureau_record.id if bureau_record else None,
            active=True
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f"Authorized account provisioned: {user.email} (Role: {user.role}, Bureau: {bureau_record.code if bureau_record else 'None'}).")

    @app.cli.command("add-institution")
    @click.option("--name", required=True, help="Official institution name")
    @click.option("--external-id", help="Verified AICTE Permanent ID (e.g. 1-123456789)")
    @click.option("--region", required=True, help="AICTE administrative region (e.g. North, West, South)")
    @click.option("--address", required=True, help="Campus address")
    @click.option("--verified", is_flag=True, default=False, help="Whether the external identifier has been officially verified")
    def add_institution(name, external_id, region, address, verified):
        """Add an authorized AICTE institution to the canonical directory."""
        if external_id:
            existing = db.session.scalar(select(Institution).where(Institution.external_id == external_id.strip()))
            if existing:
                raise click.ClickException(f"Institution with AICTE Permanent ID '{external_id}' already exists.")
        inst = Institution(
            name=name.strip(),
            external_id=external_id.strip() if external_id else None,
            verified=verified,
            region=region.strip(),
            address=address.strip()
        )
        db.session.add(inst)
        db.session.commit()
        click.echo(f"Institution added: {inst.name} (ID: {inst.id}, External ID: {inst.external_id or 'Pending verification'}, Verified: {inst.verified}).")

    @app.cli.command("grant-case")
    @click.argument("email")
    @click.argument("case_id", type=int)
    def grant_case(email, case_id):
        """Explicitly grant read access to a reviewer, auditor, or executive."""
        from .models import Complaint
        user = db.session.scalar(select(User).where(User.email == email.strip().lower()))
        if not user:
            raise click.ClickException(f"User '{email}' not found.")
        case = db.session.get(Complaint, case_id)
        if not case:
            raise click.ClickException(f"Complaint ID {case_id} not found.")
        existing = db.session.scalar(select(Grant).where(Grant.user_id == user.id, Grant.complaint_id == case.id))
        if not existing:
            db.session.add(Grant(user_id=user.id, complaint_id=case.id))
            db.session.commit()
            click.echo(f"Explicit access to case {case.reference} granted to {user.email}.")
        else:
            click.echo(f"User {user.email} already has access to case {case.reference}.")

    @app.cli.command("list-requests")
    @click.option("--status", type=click.Choice(["pending", "approved", "rejected"]), default="pending", help="Filter by request status")
    def list_requests(status):
        """List submitted account requests awaiting administrative verification."""
        from .models import AccountRequest
        reqs = db.session.scalars(select(AccountRequest).where(AccountRequest.status == status).order_by(AccountRequest.created_at)).all()
        if not reqs:
            click.echo(f"No account requests with status '{status}'.")
            return
        click.echo(f"Account requests ({status}):")
        for r in reqs:
            extra = f" | College: {r.college_name}" if r.college_name else (f" | Bureau: {r.bureau_code}" if r.bureau_code else "")
            click.echo(f"  [{r.id}] {r.name} <{r.email}> - Type: {r.request_type}{extra} | Submitted: {r.created_at}")

    @app.cli.command("review-request")
    @click.argument("request_id", type=int)
    @click.option("--decision", type=click.Choice(["approved", "rejected"]), required=True, help="Administrative review decision")
    @click.option("--reason", default="Administrative CLI review", help="Reason for approval or rejection")
    @click.option("--reviewer-email", default="admin@onecase.demo", help="Email of reviewing administrator")
    def review_request(request_id, decision, reason, reviewer_email):
        """Review and approve/reject an account request from the command line."""
        from .models import AccountRequest, Bureau, User
        from .api import event
        req = db.session.get(AccountRequest, request_id)
        if not req:
            raise click.ClickException(f"Account request ID {request_id} not found.")
        if req.status != "pending":
            raise click.ClickException(f"Account request ID {request_id} is already '{req.status}'.")
        reviewer = db.session.scalar(select(User).where(User.email == reviewer_email.strip().lower()))
        req.status = decision
        req.reviewed_at = now()
        req.reviewer_id = reviewer.id if reviewer else None
        req.reviewer_decision_reason = reason
        if decision == "approved":
            role = req.request_type
            bureau_id = None
            if req.request_type == "officer":
                bureau = db.session.scalar(select(Bureau).where(Bureau.code == (req.bureau_code or "RB").upper()))
                if not bureau:
                    bureau = db.session.scalar(select(Bureau))
                bureau_id = bureau.id if bureau else None
            user = User(name=req.name, email=req.email, role=role, bureau_id=bureau_id, password_hash=req.password_hash, active=True)
            db.session.add(user)
            db.session.flush()
            req.user_id = user.id
            event(None, "account_approved", f"Account request approved for {req.email} ({role})", reason, actor=reviewer)
            click.echo(f"Account request #{req.id} approved and provisioned as user '{user.email}' (role: {role}).")
        else:
            event(None, "account_rejected", f"Account request rejected for {req.email} ({req.request_type})", reason, actor=reviewer)
            click.echo(f"Account request #{req.id} rejected. Reason: {reason}")
        db.session.commit()
