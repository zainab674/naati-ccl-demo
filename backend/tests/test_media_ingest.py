import shutil
import uuid

import pytest
from sqlalchemy import select

from app import jobs
from app.models import Dialogue, ImportJob, Job, JobStatus
from app.services import media_ingest, media_pipeline
from app.services.imports import common, samples
from app.services.storage import get_storage


@pytest.fixture(scope="session")
def tone(tmp_path_factory):
    path = tmp_path_factory.mktemp("audio") / "tone.mp3"
    media_pipeline.run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-ac", "1", str(path)])
    return path


@pytest.fixture
def fake_downloads(monkeypatch, tone):
    """Any URL containing /ok/ downloads the test tone; anything else fails like a 404."""
    monkeypatch.setattr(common, "check_url", lambda url, timeout=10: None)

    def fake(url, dest):
        if "/ok/" not in url:
            raise media_ingest.DownloadError(f"GET {url} returned HTTP 404")
        shutil.copy(tone, dest)
        return "hash-" + url.rsplit("/", 1)[-1]

    monkeypatch.setattr(media_ingest, "download", fake)


def csv_rows(*audio_urls):
    rows = [f'm1,Clinic,Health,Easy,fil,,,{i},{"EN>LOTE" if i % 2 else "LOTE>EN"},S,S,{url},,"Text {i}",1,Meaning,ref,1,'
            for i, url in enumerate(audio_urls, start=1)]
    return (samples.DIALOGUES_HEADER + "\n" + "\n".join(rows) + "\n").encode()


def import_file(client, data):
    job = client.post("/api/admin/imports/dialogues", files={"file": ("m.csv", data, "text/csv")}).json()
    assert job["status"] == "Validated", job["report"]
    return client.post(f"/api/admin/imports/{job['id']}/commit").json()


def test_ingest_packages_encrypted_hls(admin_client, db, fake_downloads):
    done = import_file(admin_client, csv_rows("https://cdn.example.com/ok/1.mp3", "https://cdn.example.com/ok/2.mp3"))
    assert done["status"] == "ProcessingMedia" and done["progress"]["media_total"] == 2
    assert jobs.run_until_empty() == 2

    job = db.get(ImportJob, uuid.UUID(done["id"]))
    assert job.status.value == "Completed" and job.progress["media_done"] == 2
    d = db.scalar(select(Dialogue).where(Dialogue.key == "m1"))
    storage = get_storage()
    for seg in d.segments:
        assert seg.media_status == "ready" and seg.duration_seconds > 2  # tone + chime
        files = storage.list(seg.audio_file)
        names = {f.rsplit("/", 1)[1] for f in files}
        assert {"index.m3u8", "enc.key"} <= names and any(n.endswith(".ts") for n in names)
        playlist = storage.get(f"{seg.audio_file}/index.m3u8").decode()
        assert "METHOD=AES-128" in playlist and "__KEY_URI__" in playlist
        assert not any(n.endswith((".mp3", ".wav", ".m4a")) for n in names)  # no plain audio stored
        assert storage.get(seg.waveform_image).startswith(b"\x89PNG")
    assert d.estimated_duration and d.estimated_duration >= 4

    # Re-import with the same audio: no new media work queued for ready segments.
    done2 = import_file(admin_client, csv_rows("https://cdn.example.com/ok/1.mp3", "https://cdn.example.com/ok/2.mp3"))
    assert done2["progress"]["media_total"] == 0 and done2["status"] == "Completed"


def test_ingest_failure_is_reported(admin_client, db, fake_downloads):
    done = import_file(admin_client, csv_rows("https://cdn.example.com/ok/1.mp3", "https://cdn.example.com/gone/2.mp3"))
    jobs.run_until_empty(include_delayed=True)
    job = db.get(ImportJob, uuid.UUID(done["id"]))
    assert job.status.value == "Completed"
    assert job.progress["media_done"] == 1 and job.progress["media_failed"] == 1
    assert "m1 segment 2" in job.progress["failures"][0]["segment"] and "404" in job.progress["failures"][0]["error"]
    seg2 = db.scalar(select(Dialogue).where(Dialogue.key == "m1")).segments[1]
    assert seg2.media_status == "failed"
    failed = db.scalars(select(Job).where(Job.status == JobStatus.FAILED)).all()
    assert len(failed) == 1 and failed[0].attempts == 3
