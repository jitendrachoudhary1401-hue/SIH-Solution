from datetime import timedelta, timezone
from sqlalchemy import or_, select
from .models import db, Complaint, Job, Transfer, Notification, now


def monitor():
    from .api import notify, event
    active = db.session.scalars(select(Complaint).where(Complaint.status != "disposed")).all()
    for case in active:
        if case.due_at and not case.paused_at:
            due = case.due_at.replace(tzinfo=timezone.utc)
            stage = "overdue" if due < now() else "due_soon" if due <= now() + timedelta(days=2) else None
            if stage:
                key = f"deadline:{case.id}:{case.deadline_revision}:{stage}:{case.owner_id}"
                exists = db.session.scalar(select(Notification.id).where(Notification.dedup_key == key))
                notify(case.owner_id, case, stage, f"{case.reference}: {stage.replace('_', ' ')}. {case.deadline_policy}.", key)
                if not exists:
                    event(case, "deadline_alert", f"Deadline condition: {stage.replace('_', ' ')}", case.deadline_policy)
        transfers = db.session.scalars(select(Transfer).where(Transfer.complaint_id == case.id, Transfer.created_at >= now() - timedelta(days=30))).all()
        if len(transfers) >= 3:
            notify(case.owner_id, case, "bottleneck", f"{case.reference}: {len(transfers)} transfers in 30 days; illustrative threshold 3 (v1).", f"bottleneck:transfers:v1:{case.id}:{now().date()}")
        pending = [t for t in transfers if t.to_owner_id == case.owner_id and not t.acknowledged_at and t.created_at.replace(tzinfo=timezone.utc) < now() - timedelta(days=2)]
        if pending:
            notify(case.owner_id, case, "bottleneck", f"{case.reference}: transfer acknowledgement waiting more than 48 hours (illustrative v1).", f"bottleneck:ack:v1:{pending[-1].id}")
    db.session.commit()


def tick(models=None):
    from .matching import process
    eligible = or_(Job.state == "queued", (Job.state == "running") & (Job.lease_until < now()))
    # SKIP LOCKED permits multiple PostgreSQL workers. SQLite is a single-worker experiment only.
    job = db.session.scalar(select(Job).where(eligible, Job.available_at <= now()).order_by(Job.id).with_for_update(skip_locked=True).limit(1))
    if not job:
        db.session.rollback()
        return False
    job.state, job.lease_until, job.attempts = "running", now() + timedelta(minutes=15), job.attempts + 1
    case = db.session.get(Complaint, job.complaint_id)
    case.matching_state = "processing"
    job_id, case_id, revision = job.id, job.complaint_id, job.revision
    db.session.commit()
    try:
        state = process(case_id, revision, models)
        job = db.session.get(Job, job_id)
        job.state, job.error = state, None
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        job, case = db.session.get(Job, job_id), db.session.get(Complaint, case_id)
        # Store a safe operational error, never exception strings containing complaint text.
        message = "Matching failed. Check local model installation and worker logs; retry is available."
        if isinstance(error, (ImportError, FileNotFoundError)):
            message = "Local matching dependencies or model artifacts are missing. Complete model setup and retry."
        job.error, job.lease_until = message, None
        job.state = "failed" if job.attempts >= 3 else "queued"
        job.available_at = now() + timedelta(seconds=30 * 2 ** job.attempts)
        case.matching_state, case.matching_error = "failed", message
        db.session.commit()
        import logging
        logging.getLogger(__name__).error("Matching job %s failed (%s)", job_id, type(error).__name__)
    return True
