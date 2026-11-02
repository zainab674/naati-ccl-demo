"""Regressions from testing the live Vercel deployment: serverless defaults and CSV values that used to crash on commit,
or to overwrite what staff had entered."""
import pytest
from pydantic import BaseModel

from app.models import ContentStatus, Dialogue, Lesson, ScoringStatus
from app.routers import admin_students
from app.services.imports import common, dialogues, samples
from app.settings import SERVERLESS_SCRATCH_DIR, Settings, apply_serverless_defaults

DH = samples.DIALOGUES_HEADER
CH = samples.COURSES_HEADER


def d_row(key="h1", title="Clinic", seg="1", mu="1", weight="1", speaker="Receptionist"):
    return (f"{key},{title},Health,Easy,fil,,,{seg},EN>LOTE,{speaker},Receptionist,https://cdn.example.com/ok/a.mp3,,"
            f'"Your appointment is on Tuesday.",{mu},Meaning,ref,{weight},')


def c_row(no=1, title="Overview", video="", html="", free=""):
    return f"qa-c,QA course,Desc,{no},{title},{video},{html},{free}"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(common, "check_url", lambda url, timeout=10: None)


def upload_d(client, *rows):
    r = client.post("/api/admin/imports/dialogues", files={"file": ("d.csv", "\n".join([DH, *rows]).encode(), "text/csv")},
                    data={"check_urls": "false"})
    assert r.status_code == 200, r.text
    return r.json()


def upload_c(client, *rows, body=None):
    data = body if body is not None else "\n".join([CH, *rows]).encode()
    r = client.post("/api/admin/imports/courses", files={"file": ("c.csv", data, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def commit(client, job):
    r = client.post(f"/api/admin/imports/{job['id']}/commit")
    assert r.status_code == 200, r.text
    return r.json()


def errors(job, column):
    return [e for e in job["report"]["errors"] if e["column"] == column]


# ------------------------------------------------------------------ serverless defaults

def test_vercel_uses_writable_scratch_and_host_upload_limit():
    s = Settings(_env_file=None)
    apply_serverless_defaults(s, {"VERCEL": "1"})
    assert s.scratch_dir == SERVERLESS_SCRATCH_DIR
    assert s.resource_max_mb == 4 and s.content_image_max_mb == 4


def test_explicit_settings_win_on_vercel(tmp_path):
    s = Settings(_env_file=None, scratch_dir=tmp_path, resource_max_mb=2)
    apply_serverless_defaults(s, {"VERCEL": "1"})
    assert s.scratch_dir == tmp_path and s.resource_max_mb == 2


def test_other_hosts_keep_their_defaults():
    s = Settings(_env_file=None)
    before = (s.scratch_dir, s.resource_max_mb)
    apply_serverless_defaults(s, {})
    assert (s.scratch_dir, s.resource_max_mb) == before


# ------------------------------------------------------------------ dialogues.csv

@pytest.mark.parametrize("weight", ["nan", "inf", "-inf", "0", "-1", "11", "abc"])
def test_bad_meaning_unit_weights_are_invalid(admin_client, weight):
    job = upload_d(admin_client, d_row(weight=weight))
    assert job["status"] == "Invalid" and errors(job, "mu_weight")


def test_largest_allowed_weight_is_valid(admin_client):
    assert upload_d(admin_client, d_row(weight="10"))["status"] == "Validated"


def test_values_too_big_for_the_database_fail_the_dry_run(admin_client, db):
    assert errors(upload_d(admin_client, d_row(title="T" * 201)), "dialogue_title")
    assert errors(upload_d(admin_client, d_row(speaker="S" * 81)), "speaker_label")
    assert errors(upload_d(admin_client, d_row(seg="99999999999999")), "segment_no")
    assert errors(upload_d(admin_client, d_row(mu="99999999999999")), "mu_no")
    assert db.query(Dialogue).count() == 0


def test_longest_allowed_title_commits(admin_client, db):
    job = upload_d(admin_client, d_row(title="T" * 200))
    assert job["status"] == "Validated"
    commit(admin_client, job)
    assert db.query(Dialogue).count() == 1


def test_nul_byte_is_reported_not_a_crash(admin_client):
    job = upload_d(admin_client, d_row(title="a\x00b"))
    assert job["status"] == "Invalid" and "NUL" in job["report"]["errors"][0]["message"]


def test_long_field_is_read_instead_of_crashing(admin_client):
    job = upload_c(admin_client, c_row(html='"<p>' + "x" * 200_000 + '</p>"'))
    assert job["status"] == "Validated", job["report"]


def test_commit_failure_shows_no_sql(admin_client, db, monkeypatch):
    job = upload_d(admin_client, d_row())

    def boom(*a, **k):
        raise ValueError("[SQL: INSERT INTO secret_table]")
    monkeypatch.setattr(dialogues, "commit", boom)
    r = admin_client.post(f"/api/admin/imports/{job['id']}/commit")
    assert r.status_code == 500 and "SQL" not in r.text and "nothing was changed" in r.text
    assert "SQL" not in admin_client.get(f"/api/admin/imports/{job['id']}").json()["error"]


# ------------------------------------------------------------------ courses.csv

def test_course_numbers_and_lengths_fail_the_dry_run(admin_client):
    assert errors(upload_c(admin_client, c_row(no=99999999999999)), "lesson_no")
    assert errors(upload_c(admin_client, c_row(title="L" * 201)), "lesson_title")


def test_blank_cells_leave_what_staff_entered(admin_client, db):
    video = "https://www.youtube.com/watch?v=abc"
    commit(admin_client, upload_c(admin_client, c_row(video=video, html="<p>Text</p>", free="true")))
    done = commit(admin_client, upload_c(admin_client, c_row(title="Renamed")))
    assert done["counts"]["lessons_updated"] == 1
    db.expire_all()
    lesson = db.query(Lesson).one()
    assert (lesson.title, lesson.video_url, lesson.html_content, lesson.is_free) == ("Renamed", video, "<p>Text</p>", True)
    assert lesson.course.is_free is True


def test_filled_cells_still_update(admin_client, db):
    commit(admin_client, upload_c(admin_client, c_row(html="<p>Old</p>", free="true")))
    commit(admin_client, upload_c(admin_client, c_row(html="<p>New</p>", free="false")))
    db.expire_all()
    lesson = db.query(Lesson).one()
    assert lesson.html_content == "<p>New</p>" and lesson.is_free is False


def test_reimport_keeps_a_hidden_lesson_hidden_and_says_so(admin_client, db):
    commit(admin_client, upload_c(admin_client, c_row(), c_row(no=2, title="Second")))
    lesson = db.query(Lesson).filter(Lesson.lesson_number == 2).one()
    lesson.status = ContentStatus.ARCHIVED
    db.commit()
    job = upload_c(admin_client, c_row(), c_row(no=2, title="Second"))
    assert any("lesson 2 is archived" in w["message"] for w in job["report"]["warnings"])
    commit(admin_client, job)
    db.expire_all()
    assert db.query(Lesson).filter(Lesson.lesson_number == 2).one().status == ContentStatus.ARCHIVED


# ------------------------------------------------------------------ bulk students

def test_bulk_long_field_and_long_name_are_reported(admin_client):
    header = "first_name,last_name,email,language,access,access_until,target_exam_date,note\n"
    rows = f"{'N' * 101},B,long@example.com,fil,Trial,,,\nA,B,big@example.com,fil,Trial,,,\"{'x' * 200_000}\"\n"
    r = admin_client.post("/api/admin/students-import", files={"file": ("s.csv", (header + rows).encode(), "text/csv")},
                          data={"commit": "false"})
    assert r.status_code == 200, r.text
    assert {(e["row"], e["column"]) for e in r.json()["report"]["errors"]} == {(2, "first_name"), (3, "note")}


# ------------------------------------------------------------------ review queue

class _Failed(BaseModel):
    scoring_status: ScoringStatus = ScoringStatus.FAILED
    scoring_error: str = "OSError: [Errno 30] Read-only file system: '/var/task/data'"


def test_review_queue_reason_hides_technical_errors():
    assert "OSError" not in admin_students._review_reason(_Failed())
    flagged = _Failed(scoring_status=ScoringStatus.COMPLETED, scoring_error="Flagged for review: low AI confidence")
    assert admin_students._review_reason(flagged) == flagged.scoring_error
