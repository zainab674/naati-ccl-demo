"""Additional languages (MVP_SPEC module 14): seed, student language choice, filtering, scoring inputs."""
from sqlalchemy import select

from app.models import Language, LanguageScoringConfig, LanguageType, Segment
from app.services import stt
from app.services.scoring import evaluator, timing

from .conftest import signup
from .factories import make_course, make_dialogue, make_mock

NEW = {"hi": ("Hindi", "hi"), "zh": ("Mandarin", "zh"), "pa": ("Punjabi", "pa"), "ar": ("Arabic", "ar"),
       "ne": ("Nepali", "ne"), "vi": ("Vietnamese", "vi")}


def test_seed_adds_each_language_with_pair_and_guidance(client, db):
    langs = {lang.code: lang for lang in db.scalars(select(Language).where(Language.language_type == LanguageType.LOTE))}
    assert set(langs) == {"fil", *NEW}
    for code, (name, stt_code) in NEW.items():
        assert (langs[code].name, langs[code].stt_code) == (name, stt_code)
        cfg = db.scalar(select(LanguageScoringConfig).where(LanguageScoringConfig.language_id == langs[code].id))
        assert cfg.grammar_guidelines and cfg.register_guidelines and cfg.hesitation_markers
        assert cfg.pronunciation_config == {"auto_deduct": False, "review_only": True}
    public = client.get("/api/public/languages").json()
    assert [x["name"] for x in public] == sorted(x["name"] for x in public) and len(public) == 7


def test_language_chosen_at_signup_and_changed_in_account(client):
    assert signup(client, language="hi")["language"] == "hi"
    assert client.patch("/api/me", json={"language": "vi"}).json()["language"] == "vi"
    assert client.patch("/api/me", json={"language": "xx"}).status_code == 400
    assert client.patch("/api/me", json={"language": None}).json()["language"] is None


def test_signup_rejects_unknown_language(client):
    body = {"first_name": "A", "email": "a@example.com", "password": "student-pass-1", "accept_terms": True, "language": "xx"}
    assert client.post("/api/auth/signup", json=body).status_code == 400


def test_library_and_mock_tests_default_to_the_students_language(client, db):
    fil = make_dialogue(db, key="fil-1", lote="fil")
    hi1, hi2 = make_dialogue(db, key="hi-1", lote="hi"), make_dialogue(db, key="hi-2", lote="hi")
    make_mock(db, [hi1, hi2], key="mock-hi")
    signup(client, language="hi")
    rows = client.get("/api/dialogues").json()
    assert {r["title"] for r in rows} == {"Hi 1", "Hi 2"} and {r["language_name"] for r in rows} == {"Hindi"}
    assert {r["title"] for r in client.get("/api/dialogues?language=fil").json()} == {fil.title}
    assert len(client.get("/api/dialogues?language=all").json()) == 3
    assert client.get("/api/dialogues?language=xx").status_code == 400
    assert [m["language_name"] for m in client.get("/api/mock-tests").json()] == ["Hindi"]
    assert client.get("/api/mock-tests?language=fil").json() == []
    assert client.get("/api/dashboard").json()["dialogues_total"] == 2


def test_student_without_a_language_sees_everything(client, db):
    make_dialogue(db, key="fil-1", lote="fil")
    make_dialogue(db, key="ar-1", lote="ar")
    signup(client)
    assert len(client.get("/api/dialogues").json()) == 2


def test_courses_for_all_languages_and_for_one(admin_client, db):
    intro, hindi = make_course(db, key="intro"), make_course(db, key="exam-hi")
    assert admin_client.patch(f"/api/admin/courses/{hindi.id}", json={"language": "hi"}).json()["language"] == "hi"
    assert admin_client.patch(f"/api/admin/courses/{hindi.id}", json={"language": "xx"}).status_code == 400
    from fastapi.testclient import TestClient

    from app.main import app
    student = TestClient(app)
    signup(student, email="fil@example.com", language="fil")
    assert [c["title"] for c in student.get("/api/courses").json()] == ["Intro"]
    titles = {c["title"]: c["language_name"] for c in student.get("/api/courses?language=hi").json()}
    assert titles == {"Intro": None, "Exam-Hi": "Hindi"}
    assert intro.language_pair_id is None


def test_admin_dialogue_list_filters_by_language(admin_client, db):
    make_dialogue(db, key="fil-1", lote="fil")
    make_dialogue(db, key="zh-1", lote="zh")
    rows = admin_client.get("/api/admin/dialogues?language=zh").json()
    assert [(r["key"], r["language"]) for r in rows] == [("zh-1", "zh")]


def test_course_csv_language_column(admin_client, db):
    csv = (b"course_key,course_title,lesson_no,lesson_title,lote_language\n"
           b"exam-ar,Exam preparation (Arabic),1,Lesson 1,ar\n"
           b"intro,Introduction,1,Lesson 1,\n")
    job = admin_client.post("/api/admin/imports/courses", files={"file": ("c.csv", csv, "text/csv")}).json()
    assert job["report"]["ok"], job["report"]
    admin_client.post(f"/api/admin/imports/{job['id']}/commit")
    by_key = {c["key"]: c["language"] for c in admin_client.get("/api/admin/courses").json()}
    assert by_key == {"exam-ar": "ar", "intro": None}
    bad = b"course_key,course_title,lesson_no,lesson_title,lote_language\nx-1,X,1,L,klingon\n"
    rep = admin_client.post("/api/admin/imports/courses", files={"file": ("c.csv", bad, "text/csv")}).json()["report"]
    assert [e["column"] for e in rep["errors"]] == ["lote_language"]


def test_whisper_language_names_map_to_codes():
    for name, code in [("hindi", "hi"), ("chinese", "zh"), ("punjabi", "pa"), ("arabic", "ar"), ("nepali", "ne"),
                       ("vietnamese", "vi"), ("tagalog", "tl")]:
        assert stt.parse_verbose_json({"text": "x", "language": name}, "groq", "m").language == code


def test_fillers_keep_vowel_signs_and_find_chinese_markers():
    # Hindi: यानी has vowel signs (ा, ी) that a plain \w regex would strip.
    words = [{"word": "यानी,", "start": 0.5}, {"word": "डॉक्टर", "start": 1.0}, {"word": "मतलब", "start": 2.0}]
    found = timing.filler_candidates(words, "यानी, डॉक्टर मतलब", ["यानी", "मतलब", "क्या कहते हैं"])
    assert [(f["text"], f["start"]) for f in found] == [("यानी", 0.5), ("मतलब", 2.0)]
    assert [f["text"] for f in timing.filler_candidates([], "वो क्या कहते हैं, डॉक्टर", ["क्या कहते हैं"])] == ["क्या कहते हैं"]
    # Mandarin: no spaces between words, so markers are substrings.
    zh = timing.filler_candidates([], "嗯，那个医生说明天那个时间可以。", ["嗯", "那个", "就是说"])
    assert sorted(f["text"] for f in zh) == ["嗯", "那个", "那个"]
    # Arabic.
    assert [f["text"] for f in timing.filler_candidates([], "يعني الموعد يوم الثلاثاء", ["يعني"])] == ["يعني"]


def test_evaluator_prompt_uses_the_segment_language_and_its_guidance(db):
    d = make_dialogue(db, key="hi-1", lote="hi", segments=1)
    seg = db.scalar(select(Segment).where(Segment.dialogue_id == d.id))
    hi = db.scalar(select(Language).where(Language.code == "hi"))
    cfg = db.scalar(select(LanguageScoringConfig).where(LanguageScoringConfig.language_id == hi.id))
    req = evaluator.build_request(seg, "डॉक्टर", [], cfg)
    assert "from English into Hindi" in req["system"] and "आप" in req["system"]
