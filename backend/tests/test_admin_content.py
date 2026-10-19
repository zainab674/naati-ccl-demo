from sqlalchemy import select

from app.models import ContentStatus, Dialogue, Job, MeaningUnit

from .factories import make_course, make_dialogue


def test_dialogue_list_detail_and_publish_rules(admin_client, db):
    d = make_dialogue(db, status=ContentStatus.DRAFT)
    rows = admin_client.get("/api/admin/dialogues").json()
    assert rows[0]["key"] == "dlg-1" and rows[0]["segments"] == 3 and rows[0]["meaning_units"] == 6
    detail = admin_client.get(f"/api/admin/dialogues/{d.id}").json()
    assert detail["publish_problems"] == [] and len(detail["segments"]) == 3

    # A segment with failed media blocks publishing
    d.segments[1].media_status = "failed"
    db.commit()
    r = admin_client.patch(f"/api/admin/dialogues/{d.id}", json={"status": "Published"})
    assert r.status_code == 400 and "Segment 2" in r.json()["detail"]
    d.segments[1].media_status = "ready"
    db.commit()
    r = admin_client.patch(f"/api/admin/dialogues/{d.id}", json={"status": "Published", "is_free": True,
                                                                   "title": "Renamed"})
    assert r.status_code == 200 and r.json()["status"] == "Published" and r.json()["is_free"] is True
    # Hide (archive)
    assert admin_client.patch(f"/api/admin/dialogues/{d.id}", json={"status": "Archived"}).json()["status"] == "Archived"


def test_edit_segment_and_meaning_units(admin_client, db):
    d = make_dialogue(db, segments=1, mus_per_segment=3)
    seg = d.segments[0]
    mus = admin_client.get(f"/api/admin/dialogues/{d.id}").json()["segments"][0]["meaning_units"]
    r = admin_client.patch(f"/api/admin/segments/{seg.id}", json={"transcript": "New source text here"})
    assert r.json()["segments"][0]["transcript"] == "New source text here" and r.json()["version"] == 2

    # Drop MU 2, renumber MU 3 -> 2, edit MU 1, add a new MU 3
    body = [
        {"id": mus[0]["id"], "meaning_unit_number": 1, "meaning": "Edited 1", "weight": 1},
        {"id": mus[2]["id"], "meaning_unit_number": 2, "meaning": "Was three", "weight": 2},
        {"meaning_unit_number": 3, "meaning": "Brand new"},
    ]
    r = admin_client.put(f"/api/admin/segments/{seg.id}/meaning-units", json=body)
    assert r.status_code == 200, r.text
    active = sorted((m for m in r.json()["segments"][0]["meaning_units"] if m["active"]),
                    key=lambda m: m["meaning_unit_number"])
    assert [(m["meaning_unit_number"], m["meaning"]) for m in active] == [
        (1, "Edited 1"), (2, "Was three"), (3, "Brand new")]
    assert db.query(MeaningUnit).count() == 4  # the dropped MU is kept, inactive
    dup = [{"meaning_unit_number": 1, "meaning": "a"}, {"meaning_unit_number": 1, "meaning": "b"}]
    assert admin_client.put(f"/api/admin/segments/{seg.id}/meaning-units", json=dup).status_code == 400


def test_mock_tests(admin_client, db):
    a = make_dialogue(db, key="a")
    b = make_dialogue(db, key="b", status=ContentStatus.DRAFT)
    body = {"key": "mock-1", "title": "Mock 1", "dialogue_ids": [str(a.id), str(b.id)], "status": "Published"}
    r = admin_client.post("/api/admin/mock-tests", json=body)
    assert r.status_code == 400  # b is not published
    r = admin_client.post("/api/admin/mock-tests", json={**body, "status": "Draft"})
    assert r.status_code == 201 and [x["title"] for x in r.json()["dialogues"]] == ["A", "B"]
    mock_id = r.json()["id"]
    one = {**body, "status": "Draft", "dialogue_ids": [str(a.id)]}
    assert admin_client.post("/api/admin/mock-tests", json={**one, "key": "mock-2"}).status_code == 400
    b.status = ContentStatus.PUBLISHED
    db.commit()
    r = admin_client.put(f"/api/admin/mock-tests/{mock_id}", json=body)
    assert r.status_code == 200 and r.json()["status"] == "Published"


def test_courses_and_lessons(admin_client, db):
    r = admin_client.post("/api/admin/courses", json={"key": "prep", "title": "Exam Preparation"})
    cid = r.json()["id"]
    r = admin_client.post(f"/api/admin/courses/{cid}/lessons",
                          json={"title": "Numbers", "html_content": "<p>Hi<script>x</script></p>", "is_free": True})
    assert r.status_code == 201 and "<script>" not in r.json()["html_content"] and r.json()["lesson_number"] == 1
    lid = r.json()["id"]
    r = admin_client.patch(f"/api/admin/lessons/{lid}", json={"video_url": "javascript:alert(1)"})
    assert r.status_code == 400
    assert admin_client.patch(f"/api/admin/courses/{cid}", json={"status": "Published"}).json()["status"] == "Published"
    make_course(db, key="other")
    assert len(admin_client.get("/api/admin/courses").json()) == 2
    preview = admin_client.post("/api/admin/sanitize-html", json={"html": '<b onclick="x">b</b>'}).json()
    assert preview["html"] == "<b>b</b>"


def test_reprocess_media_enqueues(admin_client, db):
    d = make_dialogue(db, segments=1)
    assert admin_client.post(f"/api/admin/segments/{d.segments[0].id}/reprocess-media").json() == {"ok": True}
    assert db.query(Job).count() == 1
    db.expire_all()
    assert db.scalar(select(Dialogue)).segments[0].media_status == "pending"


def test_waveform_preview(admin_client, db):
    d = make_dialogue(db, segments=1)
    r = admin_client.get(f"/api/admin/segments/{d.segments[0].id}/waveform")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_suggest_meaning_units_mock(admin_client, db):
    d = make_dialogue(db, segments=1)
    d.segments[0].transcript = "Your appointment is on Tuesday at 10:30 in the morning."
    db.commit()
    before = db.query(MeaningUnit).count()
    r = admin_client.post(f"/api/admin/segments/{d.segments[0].id}/suggest-meaning-units")
    assert r.status_code == 200, r.text
    mus = r.json()["meaning_units"]
    assert r.json()["provider"] == "mock" and len(mus) >= 3 and mus[0]["meaning_unit_number"] == 1
    assert db.query(MeaningUnit).count() == before  # suggestions are not saved


def test_strict_schema_inlines_refs():
    from app.services.ai.llm import strict_schema
    from app.services.ai.meaning_units import Suggestion

    s = strict_schema(Suggestion.model_json_schema())
    item = s["properties"]["meaning_units"]["items"]
    assert "$defs" not in s and item["additionalProperties"] is False and item["required"] == ["meaning", "reference_interpretation"]
