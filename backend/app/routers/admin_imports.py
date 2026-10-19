"""CSV bulk import: upload -> dry-run validation report -> commit. Every upload is an ImportJob."""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..deps import CurrentUser, require_admin
from ..models import ImportJob, ImportStatus, ImportType
from ..services.imports import samples
from ..services.imports.common import MAX_CSV_BYTES, CsvError
from ..services.storage import get_storage

router = APIRouter(prefix="/api/admin/imports", tags=["admin"], dependencies=[Depends(require_admin)])


def _module(kind: ImportType):
    from ..services.imports import courses, dialogues
    return dialogues if kind == ImportType.DIALOGUES else courses


def job_dict(j: ImportJob) -> dict:
    return {"id": str(j.id), "type": j.type.value, "file_name": j.file_name, "status": j.status.value,
            "report": j.dry_run_report, "counts": j.counts, "progress": j.progress, "error": j.error,
            "created_at": j.created_at.isoformat(),
            "committed_at": j.committed_at.isoformat() if j.committed_at else None}


@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    return [job_dict(j) for j in db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(50))]


@router.get("/templates/{name}")
def template(name: str):
    files = {"dialogues-template.csv": samples.DIALOGUES_TEMPLATE, "dialogues-sample.csv": samples.DIALOGUES_SAMPLE,
             "courses-template.csv": samples.COURSES_TEMPLATE, "courses-sample.csv": samples.COURSES_SAMPLE}
    if name not in files:
        raise HTTPException(404, "Not found")
    return Response(files[name], media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/{kind}")
async def upload(kind: ImportType, file: UploadFile = File(...), check_urls: bool = Form(True),
                 cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Dry run: validate and report. Nothing is written to content tables."""
    data = await file.read(MAX_CSV_BYTES + 1)
    job = ImportJob(id=uuid.uuid4(), type=kind, file_name=(file.filename or "upload.csv")[:255],
                    status=ImportStatus.INVALID, created_by=cu.id)
    try:
        if kind == ImportType.DIALOGUES:
            report, _ = _module(kind).parse(db, data, check_remote=check_urls)
        else:
            report, _ = _module(kind).parse(db, data)
    except CsvError as e:
        job.dry_run_report = {"ok": False, "error_count": 1, "warning_count": 0, "summary": {}, "warnings": [],
                              "errors": [{"row": None, "column": "", "message": str(e)}]}
    else:
        job.dry_run_report = report.as_dict()
        job.status = ImportStatus.VALIDATED if report.ok else ImportStatus.INVALID
        job.file_key = f"imports/{job.id}.csv"
        get_storage().put(job.file_key, data, "text/csv")
    job.dry_run_report["check_urls"] = check_urls
    db.add(job)
    db.commit()
    return job_dict(job)


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(404, "Import not found")
    return job_dict(job)


@router.post("/{job_id}/commit")
def commit(job_id: uuid.UUID, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
    if not job:
        raise HTTPException(404, "Import not found")
    if job.status != ImportStatus.VALIDATED:
        raise HTTPException(409, f"Only a validated import can be committed (status: {job.status.value})")
    job.status = ImportStatus.COMMITTING
    db.commit()
    data = get_storage().get(job.file_key) or b""
    module = _module(job.type)
    try:
        # Re-validate: content may have changed since the dry run. URLs were checked at dry-run time.
        report, parsed = (module.parse(db, data, check_remote=False) if job.type == ImportType.DIALOGUES
                          else module.parse(db, data))
        if not report.ok:
            job.status, job.error = ImportStatus.FAILED, "Validation failed on commit; upload the file again."
            job.dry_run_report = {**report.as_dict(), "check_urls": False}
            db.commit()
            return job_dict(job)
        counts = module.commit(db, parsed, created_by=cu.id)
    except Exception as e:
        db.rollback()
        job = db.get(ImportJob, job_id)
        job.status, job.error = ImportStatus.FAILED, f"{type(e).__name__}: {e}"[:2000]
        db.commit()
        raise HTTPException(500, f"Import failed: {job.error}") from e
    media_ids = counts.pop("media_segment_ids", [])
    job = db.get(ImportJob, job_id)
    job.counts, job.committed_at = counts, utcnow()
    job.progress = {"media_total": len(media_ids), "media_done": 0, "media_failed": 0}
    job.status = ImportStatus.COMPLETED
    db.commit()
    return job_dict(job)
