import pytest
from sqlalchemy import select

from app.models import ContentStatus, Dialogue, Direction, ImportJob, MeaningUnit, Segment
from app.services.imports import common, samples

HEADER = samples.DIALOGUES_HEADER


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """URL checks: everything under https://cdn.example.com/ok/ is reachable, the rest is not."""
    monkeypatch.setattr(common, "check_url", lambda url, timeout=10: None if "/ok/" in url else "HTTP 404")


def row(key="d1", seg=1, mu=1, direction="EN>LOTE", audio="https://cdn.example.com/ok/a1.mp3", meaning="MU meaning",
        transcript="Your appointment is on Tuesday.", difficulty="Easy", title="Clinic", topic="Health", lang="fil"):
    return (f'{key},{title},{topic},{difficulty},{lang},,,{seg},{direction},Receptionist,Receptionist,{audio},,'
            f'"{transcript}",{mu},{meaning},ref,1,')


def csv(*rows):
    return (HEADER + "\n" + "\n".join(rows) + "\n").encode()


def upload(client, data, check_urls=True):
    r = client.post("/api/admin/imports/dialogues", files={"file": ("d.csv", data, "text/csv")},
                    data={"check_urls": str(check_urls).lower()})
    assert r.status_code == 200, r.text
    return r.json()


def test_templates_download(admin_client):
    r = admin_client.get("/api/admin/imports/templates/dialogues-sample.csv")
    assert r.status_code == 200 and r.text.startswith("dialogue_key,")


def test_sample_file_validates_structure(admin_client):
    job = upload(admin_client, samples.DIALOGUES_SAMPLE.encode(), check_urls=False)
    assert job["status"] == "Validated", job["report"]["errors"]
    assert job["report"]["summary"]["segments"] == 2 and job["report"]["summary"]["meaning_units"] == 6


def test_dry_run_reports_errors(admin_client, db):
    data = csv(
        row(mu=1),
        row(mu=1),                                        # duplicate key
        row(mu=2, difficulty="Hard"),                     # bad enum
        row(seg=2, mu=1, direction="EN-LOTE"),            # bad direction
        row(seg=3, mu=1, audio="https://cdn.example.com/missing.mp3"),  # unreachable
        row(seg=4, mu=1, lang="xx"),                      # unknown language
        row(seg=5, mu=1, meaning=""),                     # missing field
        row(seg=1, mu=3, title="Other title"),            # inconsistent dialogue field
    )
    job = upload(admin_client, data)
    assert job["status"] == "Invalid"
    msgs = {(e["row"], e["column"]) for e in job["report"]["errors"]}
    assert (3, "mu_no") in msgs
    assert (4, "difficulty") in msgs
    assert (5, "direction") in msgs
    assert (6, "audio_url") in msgs
    assert (7, "lote_language") in msgs
    assert (8, "meaning") in msgs
    assert (9, "dialogue_title") in msgs
    assert db.query(Dialogue).count() == 0  # dry run wrote nothing
    # an invalid import cannot be committed
    assert admin_client.post(f"/api/admin/imports/{job['id']}/commit").status_code == 409


def test_missing_column_and_encoding(admin_client):
    job = upload(admin_client, b"dialogue_key,dialogue_title\nx,y\n")
    assert job["status"] == "Invalid" and "Missing column" in job["report"]["errors"][0]["message"]
    job = upload(admin_client, "dialogue_key\n\xe9".encode("latin-1"))
    assert "UTF-8" in job["report"]["errors"][0]["message"]


def test_commit_and_idempotent_reimport(admin_client, db):
    data = csv(row(mu=1), row(mu=2, meaning="On Tuesday"),
               row(seg=2, mu=1, direction="LOTE>EN", transcript="Pwede po ba sa hapon?",
                   audio="https://cdn.example.com/ok/a2.mp3"))
    job = upload(admin_client, data)
    assert job["status"] == "Validated", job["report"]
    done = admin_client.post(f"/api/admin/imports/{job['id']}/commit").json()
    assert done["status"] == "ProcessingMedia"
    assert done["counts"]["dialogues_created"] == 1 and done["counts"]["meaning_units_created"] == 3
    d = db.scalar(select(Dialogue).where(Dialogue.key == "d1"))
    assert d.status == ContentStatus.DRAFT and d.version == 1 and d.topic.name == "Health"
    assert [s.direction for s in d.segments] == [Direction.EN_TO_LOTE, Direction.LOTE_TO_EN]
    assert d.segments[0].target_language.code == "fil" and d.segments[1].target_language.code == "en"

    # Same file again: nothing duplicated, nothing changed.
    job2 = upload(admin_client, data)
    done2 = admin_client.post(f"/api/admin/imports/{job2['id']}/commit").json()
    assert done2["counts"]["dialogues_created"] == 0 and done2["counts"]["dialogues_updated"] == 0
    assert db.query(Segment).count() == 2 and db.query(MeaningUnit).count() == 3

    # Edited file: MU text changed, MU 2 removed -> updated + deactivated, version bumped.
    data3 = csv(row(mu=1, meaning="There is an appointment"),
                row(seg=2, mu=1, direction="LOTE>EN", transcript="Pwede po ba sa hapon?",
                    audio="https://cdn.example.com/ok/a2.mp3"))
    job3 = upload(admin_client, data3)
    done3 = admin_client.post(f"/api/admin/imports/{job3['id']}/commit").json()
    assert done3["counts"]["meaning_units_updated"] == 1 and done3["counts"]["meaning_units_deactivated"] == 1
    db.expire_all()
    d = db.scalar(select(Dialogue).where(Dialogue.key == "d1"))
    assert d.version == 2
    assert db.query(MeaningUnit).count() == 3  # deactivated, not deleted
    assert db.scalar(select(ImportJob).where(ImportJob.id == job3["id"])).committed_at is not None

    # A committed job cannot be committed twice
    assert admin_client.post(f"/api/admin/imports/{job3['id']}/commit").status_code == 409


def test_import_requires_admin(student_client):
    r = student_client.post("/api/admin/imports/dialogues", files={"file": ("d.csv", csv(row()), "text/csv")})
    assert r.status_code == 403
