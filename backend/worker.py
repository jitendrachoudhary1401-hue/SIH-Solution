import argparse
import time
import logging
from uuid import uuid4
from app import create_app
from app.jobs import monitor, tick
from app.documents import scan_pending

WORKER_ID = uuid4().hex

def run_cycle():
    from app.models import db, now, WorkerHeartbeat
    processed = False
    failed = []
    for task in (tick, monitor, scan_pending):
        try:
            result = task()
            if task is tick:
                processed = bool(result)
        except Exception as error:
            db.session.rollback()
            failed.append(getattr(task, "__name__", "stage"))
            logging.getLogger(__name__).error("Worker stage %s failed (%s)", getattr(task, "__name__", "stage"), type(error).__name__)
    try:
        heartbeat = db.session.get(WorkerHeartbeat, WORKER_ID)
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(id=WORKER_ID)
            db.session.add(heartbeat)
        heartbeat.seen_at, heartbeat.failed_stages = now(), failed
        if not failed:
            heartbeat.succeeded_at = now()
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        logging.getLogger(__name__).error("Worker heartbeat unavailable (%s)", type(error).__name__)
    return processed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process queued jobs once, run monitoring, and exit")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        while True:
            processed = run_cycle()
            if args.once:
                while processed:
                    processed = run_cycle()
                break
            time.sleep(2 if processed else 30)


if __name__ == "__main__":
    main()
