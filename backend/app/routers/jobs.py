"""Runs queued jobs (scoring, audio processing) on hosts without a worker process (Vercel). The site calls
POST /api/jobs/tick while something is waiting; the scheduler calls GET /api/cron/jobs as a backstop. Each call works
for at most JOBS_TICK_SECONDS so it ends inside the host's request time limit."""
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select

from ..db import SessionLocal, utcnow
from ..deps import CurrentUser, current_user
from ..jobs import run_one
from ..models import Job, JobStatus
from ..settings import get_settings

router = APIRouter(prefix="/api", tags=["jobs"])


def _due() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Job).where(
            Job.status == JobStatus.QUEUED, Job.run_after <= utcnow())) or 0


def _run(budget: float) -> dict:
    end, ran = time.monotonic() + budget, 0
    while time.monotonic() < end and run_one():
        ran += 1
    return {"ran": ran, "pending": _due()}


@router.post("/jobs/tick")
def tick(_: CurrentUser = Depends(current_user)):
    return _run(get_settings().jobs_tick_seconds)


@router.get("/cron/jobs")
def cron(authorization: str = Header("")):
    secret = get_settings().cron_secret
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(401, "Not allowed")
    return _run(get_settings().jobs_tick_seconds)
