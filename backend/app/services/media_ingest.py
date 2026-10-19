"""Import media ingest (background job per segment): download the audio from its CSV URL, package it as encrypted
HLS, store the package and a waveform image in object storage, and report progress on the ImportJob."""
import hashlib
import logging
import shutil
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..jobs import enqueue, handler, on_failure
from ..models import ImportJob, ImportStatus, Segment
from ..settings import get_settings
from . import media_pipeline
from .storage import get_storage

log = logging.getLogger("media_ingest")
JOB_KIND = "ingest_segment_media"
CONTENT_TYPES = {".m3u8": "application/vnd.apple.mpegurl", ".ts": "video/mp2t", ".key": "application/octet-stream"}


class DownloadError(RuntimeError):
    pass


def download(url: str, dest: Path) -> str:
    """Stream a URL to dest with a size cap. Returns the sha256 of the content."""
    max_bytes = get_settings().media_download_max_mb * 1024 * 1024
    digest, size = hashlib.sha256(), 0
    with httpx.stream("GET", url, follow_redirects=True, timeout=60) as r:
        if r.status_code >= 400:
            raise DownloadError(f"GET {url} returned HTTP {r.status_code}")
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise DownloadError(f"File is larger than {max_bytes // (1024 * 1024)} MB")
                digest.update(chunk)
                f.write(chunk)
    if size == 0:
        raise DownloadError("Downloaded file is empty")
    return digest.hexdigest()


def enqueue_for_import(db: Session, job: ImportJob, segment_ids: list[str]) -> None:
    for sid in segment_ids:
        enqueue(db, JOB_KIND, {"segment_id": sid, "import_job_id": str(job.id)})
    job.progress = {"media_total": len(segment_ids), "media_done": 0, "media_failed": 0, "failures": []}
    job.status = ImportStatus.PROCESSING_MEDIA if segment_ids else ImportStatus.COMPLETED


def _report(import_job_id: str | None, ok: bool, segment_label: str = "", error: str = "") -> None:
    if not import_job_id:
        return
    with SessionLocal() as db:
        job = db.scalar(select(ImportJob).where(ImportJob.id == uuid.UUID(import_job_id)).with_for_update())
        if not job:
            return
        p = dict(job.progress or {})
        p["media_done" if ok else "media_failed"] = p.get("media_done" if ok else "media_failed", 0) + 1
        if not ok:
            p["failures"] = [*p.get("failures", []), {"segment": segment_label, "error": error[:300]}][:100]
        job.progress = p
        if p.get("media_done", 0) + p.get("media_failed", 0) >= p.get("media_total", 0):
            job.status = ImportStatus.COMPLETED
            if p.get("media_failed"):
                job.error = f"{p['media_failed']} segment(s) failed audio processing; fix the URL(s) and re-import."
        db.commit()


def _label(seg: Segment) -> str:
    return f"{seg.dialogue.key} segment {seg.segment_number}"


@handler(JOB_KIND)
def ingest_segment(payload: dict) -> None:
    settings = get_settings()
    storage = get_storage()
    with SessionLocal() as db:
        seg = db.get(Segment, uuid.UUID(payload["segment_id"]))
        if not seg:
            return
        seg.media_status, seg.media_error = "processing", ""
        db.commit()
        work = settings.scratch_dir / f"ingest-{seg.id.hex[:12]}-{uuid.uuid4().hex[:6]}"
        work.mkdir(parents=True, exist_ok=True)
        try:
            src = work / "source"
            audio_hash = download(seg.source_audio_url, src)
            unchanged = audio_hash == seg.source_audio_hash and seg.audio_file and storage.exists(
                f"{seg.audio_file}/index.m3u8")
            if not unchanged:
                prefix = f"media/{seg.id}/{audio_hash[:12]}"
                out = work / "hls"
                duration = media_pipeline.package_hls(src, out)
                for f in sorted(out.iterdir()):
                    storage.put(f"{prefix}/{f.name}", f.read_bytes(), CONTENT_TYPES.get(f.suffix))
                old = seg.audio_file
                seg.audio_file, seg.source_audio_hash, seg.duration_seconds = prefix, audio_hash, duration
                if old and old != prefix:
                    storage.delete_prefix(old)

            # Waveform: the image from the CSV when given, else drawn from the audio.
            png = work / "waveform.png"
            if seg.waveform_source_url:
                download(seg.waveform_source_url, png)
            else:
                media_pipeline.waveform_png(src, png)
            waveform_key = f"waveforms/{seg.id}.png"
            storage.put(waveform_key, png.read_bytes(), "image/png")
            seg.waveform_image = waveform_key
            seg.media_status = "ready"
            dialogue = seg.dialogue
            dialogue.estimated_duration = int(sum(s.duration_seconds or 0 for s in dialogue.segments if s.active))
            db.commit()
            label = _label(seg)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    log.info("media ready: %s", label)
    _report(payload.get("import_job_id"), ok=True)


@on_failure(JOB_KIND)
def ingest_failed(payload: dict, error: str) -> None:
    with SessionLocal() as db:
        seg = db.get(Segment, uuid.UUID(payload["segment_id"]))
        if not seg:
            return
        seg.media_status, seg.media_error = "failed", error.splitlines()[0][:500]
        label = _label(seg)
        db.commit()
    _report(payload.get("import_job_id"), ok=False, segment_label=label, error=error.splitlines()[0])
