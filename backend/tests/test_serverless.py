"""Pieces for serverless hosts (Vercel): files in the database, and running queued jobs from a request."""
from app.jobs import enqueue, handler
from app.models import Job, JobStatus
from app.services.storage import DbStorage
from app.settings import get_settings


def test_db_storage_put_get_list_delete():
    st = DbStorage()
    st.put("media/a_1/v1/index.m3u8", b"#EXTM3U")
    st.put("media/a_1/v1/seg0.ts", b"\x00\x01")
    st.put("media/a_10/v1/seg0.ts", b"x")  # must not match prefix media/a_1
    st.put("media/a_1/v1/seg0.ts", b"\x02")  # overwrite
    assert st.get("media/a_1/v1/seg0.ts") == b"\x02"
    assert st.get("missing") is None
    assert st.list("media/a_1") == ["media/a_1/v1/index.m3u8", "media/a_1/v1/seg0.ts"]
    st.delete("media/a_1/v1/index.m3u8")
    assert not st.exists("media/a_1/v1/index.m3u8")
    st.delete_prefix("media/a_1")
    assert st.list("media/a_1") == []
    assert st.get("media/a_10/v1/seg0.ts") == b"x"


def test_jobs_tick_runs_queued_jobs(student_client, db):
    done = []
    handler("test_tick")(lambda payload: done.append(payload["n"]))
    enqueue(db, "test_tick", {"n": 1})
    enqueue(db, "test_tick", {"n": 2})
    db.commit()
    r = student_client.post("/api/jobs/tick")
    assert r.status_code == 200 and r.json() == {"ran": 2, "pending": 0}
    assert sorted(done) == [1, 2]
    db.expire_all()
    assert {j.status for j in db.query(Job).all()} == {JobStatus.DONE}


def test_jobs_tick_needs_sign_in(client):
    assert client.post("/api/jobs/tick").status_code == 401


def test_cron_needs_secret(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cron_secret", "s3cret-value")
    assert client.get("/api/cron/jobs").status_code == 401
    assert client.get("/api/cron/jobs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = client.get("/api/cron/jobs", headers={"Authorization": "Bearer s3cret-value"})
    assert r.status_code == 200 and r.json()["ran"] == 0
