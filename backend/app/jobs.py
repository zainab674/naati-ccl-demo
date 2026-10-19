"""Background jobs on a Postgres table (SELECT ... FOR UPDATE SKIP LOCKED): no extra infrastructure, survives
restarts, safe with several worker processes. Run workers with `python -m app.worker`."""
import logging
import traceback
import uuid
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal, utcnow
from .models import Job, JobStatus

log = logging.getLogger("jobs")

HANDLERS: dict[str, Callable[[dict], None]] = {}


def handler(kind: str):
    def register(fn: Callable[[dict], None]):
        HANDLERS[kind] = fn
        return fn
    return register


def enqueue(db: Session, kind: str, payload: dict, max_attempts: int = 3, delay_seconds: float = 0) -> Job:
    """Adds the job to the session; it becomes visible to workers when the caller commits."""
    job = Job(id=uuid.uuid4(), kind=kind, payload=payload, max_attempts=max_attempts,
              run_after=utcnow() + timedelta(seconds=delay_seconds))
    db.add(job)
    return job


def _claim(db: Session) -> Job | None:
    job = db.scalar(select(Job).where(Job.status == JobStatus.QUEUED, Job.run_after <= utcnow())
                    .order_by(Job.run_after).limit(1).with_for_update(skip_locked=True))
    if job:
        job.status, job.attempts = JobStatus.RUNNING, job.attempts + 1
        db.commit()
    return job


def run_one() -> bool:
    """Claim and run one due job. Returns False when there was nothing to do."""
    _register_handlers()
    with SessionLocal() as db:
        job = _claim(db)
        if not job:
            return False
        job_id, kind, payload = job.id, job.kind, dict(job.payload)
        attempt, max_attempts = job.attempts, job.max_attempts
    fn = HANDLERS.get(kind)
    error = None
    try:
        if not fn:
            raise RuntimeError(f"No handler for job kind {kind!r}")
        fn(payload)
    except Exception as e:  # noqa: BLE001
        log.exception("job %s (%s) failed on attempt %s", job_id, kind, attempt)
        error = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=5)}"[:4000]
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if error is None:
            job.status, job.finished_at, job.last_error = JobStatus.DONE, utcnow(), ""
        elif attempt < max_attempts:
            # Exponential backoff: 10 s, 40 s, 90 s ...
            job.status, job.last_error = JobStatus.QUEUED, error
            job.run_after = utcnow() + timedelta(seconds=10 * attempt * attempt)
        else:
            job.status, job.finished_at, job.last_error = JobStatus.FAILED, utcnow(), error
            on_fail = FAILURE_HOOKS.get(kind)
            if on_fail:
                try:
                    on_fail(payload, error)
                except Exception:  # noqa: BLE001
                    log.exception("failure hook for %s failed", kind)
        db.commit()
    return True


def run_until_empty(limit: int = 1000, include_delayed: bool = False) -> int:
    """Tests and scripts: run due jobs synchronously. include_delayed also runs jobs waiting for a retry."""
    n = 0
    while n < limit:
        if include_delayed:
            with SessionLocal() as db:
                for job in db.scalars(select(Job).where(Job.status == JobStatus.QUEUED)):
                    job.run_after = utcnow()
                db.commit()
        if not run_one():
            break
        n += 1
    return n


# Called once when a job has used all its attempts (e.g. mark the segment as failed).
FAILURE_HOOKS: dict[str, Callable[[dict, str], None]] = {}


def on_failure(kind: str):
    def register(fn):
        FAILURE_HOOKS[kind] = fn
        return fn
    return register


_registered = False


def _register_handlers() -> None:
    """Import the modules that define handlers (kept lazy to avoid import cycles)."""
    global _registered
    if not _registered:
        from .services import media_ingest  # noqa: F401
        _registered = True
