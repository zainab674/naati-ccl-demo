"""Load DEMO data into a development database, for trying the app and client walkthroughs.

    python -m app.demo_data           # add demo content, students and scored attempts (skips what already exists)
    python -m app.demo_data --reset   # remove all demo data again

Refuses to run when ENVIRONMENT=production. Everything it creates is marked DEMO (keys start with "demo-", students
use @example.com addresses). Audio is synthetic (speech-like tones), packaged through the real encrypted-HLS pipeline
so the test player works. Scoring runs through the real pipeline with stand-in speech-to-text and evaluator (no API
calls, no cost), so results show every kind of feedback: correct, omitted and distorted meaning units, a grammar error,
a hesitation, and start delays / long pauses measured from the audio by the real timing analysis.
Demo student password: DEMO_PASSWORD (see .env.example).
"""
import array
import logging
import math
import random
import re
import sys
import tempfile
import uuid
import zlib
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import demo_content as C
from .demo_voice import speak
from .db import SessionLocal, utcnow
from .models import (ContentStatus, Course, CourseChapter, Dialogue, DialogueAttempt, Difficulty, Job, Lesson, MeaningUnit,
                     MockTest, MockTestAttempt, MockTestDialogue, Resource, ResourceType, Segment, SegmentAttempt,
                     Subscription, SubscriptionStatus, Topic, User, UserRole)
from .security import hash_password
from .services import attempts as svc
from .services import languages, media_pipeline
from .services import resources as resource_svc
from .services.storage import get_storage
from .settings import get_settings

log = logging.getLogger("demo")
RATE = 16000


# ------------------------------------------------------------------ synthetic audio

def speech_like_wav(path: Path, words: int, *, lead: float = 0.6, pause_at: float | None = None, pause: float = 0.0,
                    pitch: float = 150.0, seed: int = 0) -> float:
    """Write a 16 kHz mono WAV of syllable-shaped harmonic bursts (not real speech). Returns its duration."""
    rnd = random.Random(seed)
    samples = array.array("h", [0] * int(lead * RATE))
    for w in range(words):
        if pause_at is not None and w == int(words * pause_at):
            samples.extend([0] * int(pause * RATE))
        for _ in range(rnd.choice((1, 1, 2, 2, 3))):
            n = int(rnd.uniform(0.12, 0.22) * RATE)
            f0 = pitch * rnd.uniform(0.85, 1.2)
            for i in range(n):
                env = math.sin(math.pi * i / n) ** 0.6
                t = i / RATE
                v = sum(math.sin(2 * math.pi * f0 * k * t) / k for k in (1, 2, 3, 4))
                samples.append(int(9000 * env * v / 2))
            samples.extend([0] * int(0.04 * RATE))
        samples.extend([0] * int(rnd.uniform(0.08, 0.16) * RATE))
    samples.extend([0] * int(0.4 * RATE))
    import wave
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(samples.tobytes())
    return len(samples) / RATE


def _words(text: str) -> int:
    # Chinese has no spaces: count characters as roughly half a word each.
    cjk = len(re.findall(r"[㐀-鿿]", text))
    return max(3, len(text.split()) + cjk // 2)


# ------------------------------------------------------------------ content

def _nice(ref: str) -> str:
    """References are stored lowercase in demo_content for matching; show them as sentences."""
    if ref and ref[0].isascii():
        ref = re.sub(r"\bi\b", "I", ref)
        ref = ref[0].upper() + ref[1:]
    return ref


def _package(db: Session, seg: Segment, text: str, seed: int, lang: str, female: bool) -> None:
    storage = get_storage()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "source.wav"
        if speak(src, [text], lang, female) is None:  # offline: synthetic tones instead of speech
            speech_like_wav(src, _words(text), pitch=130 if seg.segment_number % 2 else 190, seed=seed)
        out = Path(tmp) / "hls"
        duration = media_pipeline.package_hls(src, out)
        prefix = f"media/{seg.id}/demo"
        for f in sorted(out.iterdir()):
            storage.put(f"{prefix}/{f.name}", f.read_bytes())
        png = Path(tmp) / "wave.png"
        media_pipeline.waveform_png(src, png)
        storage.put(f"waveforms/{seg.id}.png", png.read_bytes(), "image/png")
    seg.audio_file, seg.waveform_image, seg.duration_seconds = prefix, f"waveforms/{seg.id}.png", duration
    seg.media_status, seg.source_audio_url = "ready", "demo://tts"


def load_dialogues(db: Session) -> None:
    en = languages.english(db)
    lotes = languages.lotes_by_code(db)
    for i, spec in enumerate(C.DIALOGUES):
        if db.scalar(select(Dialogue).where(Dialogue.key == spec["key"])):
            continue
        lote = lotes[spec["lote"]]
        pair = languages.get_or_create_pair(db, en, lote)
        topic = db.scalar(select(Topic).where(Topic.name == spec["topic"]))
        d = Dialogue(key=spec["key"], title=spec["title"], topic_id=topic.id if topic else None, language_pair_id=pair.id,
                     description=spec["description"], difficulty=Difficulty(spec["difficulty"]), is_free=spec["is_free"],
                     status=ContentStatus.PUBLISHED, sort_order=100 + i,
                     instructions="DEMO dialogue: synthetic audio and unreviewed translations.")
        db.add(d)
        db.flush()
        for n, (direction, role, transcript, mus) in enumerate(spec["segments"], start=1):
            src, tgt = (en, lote) if direction == C.EN else (lote, en)
            seg = Segment(dialogue_id=d.id, segment_number=n, source_language_id=src.id, target_language_id=tgt.id,
                          transcript=transcript, speaker_label=role, speaker_role=role, word_count=len(transcript.split()))
            db.add(seg)
            db.flush()
            for m, mu in enumerate(mus, start=1):
                db.add(MeaningUnit(segment_id=seg.id, meaning_unit_number=m, meaning=mu[0],
                                   reference_interpretation=_nice(mu[1]), reference_language_id=tgt.id))
            # The professional speaks English, the client the LOTE; voices alternate by dialogue.
            english = direction == C.EN
            _package(db, seg, transcript, seed=i * 10 + n, lang="en" if english else spec["lote"],
                     female=(i % 2 == 0) == english)
        d.estimated_duration = int(sum(s.duration_seconds or 0 for s in d.segments))
        db.commit()
        log.info("dialogue %s", spec["key"])
    for spec in C.MOCK_TESTS:
        if db.scalar(select(MockTest).where(MockTest.key == spec["key"])):
            continue
        ds = [db.scalar(select(Dialogue).where(Dialogue.key == k)) for k in spec["dialogues"]]
        m = MockTest(key=spec["key"], title=spec["title"], language_pair_id=ds[0].language_pair_id,
                     status=ContentStatus.PUBLISHED, sort_order=100)
        db.add(m)
        db.flush()
        for pos, d in enumerate(ds, start=1):
            db.add(MockTestDialogue(mock_test_id=m.id, dialogue_id=d.id, position=pos))
        db.commit()
        log.info("mock test %s", spec["key"])


def load_courses(db: Session) -> None:
    lotes = languages.lotes_by_code(db)
    for spec in C.COURSES:
        if db.scalar(select(Course).where(Course.key == spec["key"])):
            continue
        pair = languages.pair_for(db, lotes[spec["lote"]]) if spec["lote"] else None
        c = Course(key=spec["key"], title=spec["title"], description=spec["description"], status=ContentStatus.PUBLISHED,
                   is_free=spec["is_free"], sort_order=100, language_pair_id=pair.id if pair else None)
        db.add(c)
        db.flush()
        n = 0
        for ch_no, (ch_title, lessons) in enumerate(spec["chapters"], start=1):
            ch = CourseChapter(course_id=c.id, number=ch_no, title=ch_title)
            db.add(ch)
            db.flush()
            for title, html in lessons:
                n += 1
                db.add(Lesson(course_id=c.id, chapter_id=ch.id, lesson_number=n, title=title, html_content=html,
                              is_free=spec["is_free"] or (spec.get("free_first_lesson") and n == 1),
                              status=ContentStatus.PUBLISHED))
        db.commit()
        log.info("course %s", spec["key"])


def _pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with plain text lines."""
    text = "BT /F1 13 Tf 50 780 Td 18 TL " + " ".join(f"({ln.replace('(', '[').replace(')', ']')}) '" for ln in lines) + " ET"
    objs = ["<</Type/Catalog/Pages 2 0 R>>", "<</Type/Pages/Kids[3 0 R]/Count 1>>",
            "<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            f"<</Length {len(text)}>>stream\n{text}\nendstream", "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out.encode("latin-1")))
        out += f"{i} 0 obj{o}endobj\n"
    xref = len(out.encode("latin-1"))
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer<</Size {len(objs) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def load_hub(db: Session) -> None:
    lotes = languages.lotes_by_code(db)
    for i, spec in enumerate(C.HUB):
        if db.scalar(select(Resource).where(Resource.key == spec["key"])):
            continue
        pair = languages.pair_for(db, lotes[spec["lote"]]) if spec["lote"] else None
        topic = db.scalar(select(Topic).where(Topic.name == spec["topic"])) if spec["topic"] else None
        r = Resource(key=spec["key"], title=spec["title"], description=spec["description"],
                     resource_type=ResourceType(spec["type"]), language_pair_id=pair.id if pair else None,
                     topic_id=topic.id if topic else None, is_free=spec["is_free"], sort_order=100 + i,
                     status=ContentStatus.PUBLISHED, html_content=spec.get("html", ""), external_url=spec.get("url", ""))
        db.add(r)
        db.flush()
        if spec.get("pdf_lines"):
            resource_svc.store_file(r, spec["key"] + ".pdf", _pdf(spec["pdf_lines"]))
        db.commit()
        log.info("resource %s", spec["key"])


# ------------------------------------------------------------------ students and scored attempts

QUALITY = {  # how a demo student performs: (omit every Nth MU or 0, distort?, grammar slip?, hesitation?, delays)
    "excellent": (0, False, False, False, {}),
    "good": (0, True, True, False, {}),
    "mixed": (3, True, True, True, {"delay": {3}, "pause": {1}}),
    "weak": (2, True, False, True, {"delay": {0, 2}, "pause": {1, 3}}),
}
DISTORTIONS = {_nice(mu[1]): _nice(mu[2]) for d in C.DIALOGUES for s in d["segments"] for mu in s[3] if len(mu) > 2}
SLIPS = {_nice(k): v for k, v in C.GRAMMAR_SLIPS.items()}
TRANSCRIPTS: dict[uuid.UUID, str] = {}  # segment attempt id -> what the demo student "said"


def _answer(sa, quality: str, seg_index: int) -> str:
    every, distort, slip, hesitate, _ = QUALITY[quality]
    parts = []
    for k, mu in enumerate([m for m in sa.segment.meaning_units if m.active], start=1):
        ref = mu.reference_interpretation
        if every and (seg_index + k) % every == 0:
            continue  # omitted
        if distort and ref in DISTORTIONS and seg_index == 0:
            parts.append(DISTORTIONS[ref])
        elif slip and ref in SLIPS:
            parts.append(SLIPS[ref][0])
        else:
            parts.append(ref)
    # One spoken sentence: only the first phrase keeps its capital letter.
    parts = [p if i == 0 or not p[:1].isascii() else p[:1].lower() + p[1:] for i, p in enumerate(parts)]
    text = re.sub(r"i", "I", " ".join(parts)) or "..."
    return ("um um " + text) if hesitate and seg_index == 1 else text


def _demo_evaluator(system: str, user: str, schema: dict) -> dict:
    """Stand-in evaluator for the demo: text matching plus the demo's planted distortions, slips and fillers."""
    import json

    from .services.scoring.evaluator import _norm
    data = json.loads(user)
    t = _norm(data["candidate_transcript"])
    items, lq, fl = [], [], []
    for m in data["meaning_units"]:
        ref = m["reference_rendering"]
        slip = SLIPS.get(ref)
        if _norm(ref) and _norm(ref) in t:
            items.append({"meaning_unit": m["meaning_unit"], "result": "correct", "student_interpretation": ref,
                          "explanation": "", "suggested_version": ref, "confidence": 0.9})
        elif slip and _norm(slip[0]) in t:
            items.append({"meaning_unit": m["meaning_unit"], "result": "correct", "student_interpretation": slip[0],
                          "explanation": "", "suggested_version": ref, "confidence": 0.85})
            lq.append({"error": "grammar", "student_text": slip[0], "suggested_version": slip[1], "explanation": slip[2],
                       "confidence": 0.8})
        elif ref in DISTORTIONS and _norm(DISTORTIONS[ref]) in t:
            items.append({"meaning_unit": m["meaning_unit"], "result": "distortion", "student_interpretation": DISTORTIONS[ref],
                          "explanation": f'The meaning changed: "{m["meaning"]}" was rendered differently.',
                          "suggested_version": ref, "confidence": 0.85})
        else:
            items.append({"meaning_unit": m["meaning_unit"], "result": "omission", "student_interpretation": "",
                          "explanation": f'"{m["meaning"]}" was not interpreted.', "suggested_version": ref, "confidence": 0.85})
    if "um um" in t:
        fl.append({"error": "hesitation", "transcript_excerpt": "um um", "explanation": "Repeated filler before starting.",
                   "confidence": 0.8})
    return {"meaning_units": items, "insertions": [], "language_quality": lq, "fluency": fl,
            "transcript_quality": "good", "confidence": 0.85,
            "overall_feedback": "DEMO feedback from a stand-in evaluator (no AI was called)."}


def _record(sa, quality: str, seg_index: int, seed: int) -> None:
    _, _, _, _, timing = QUALITY[quality]
    text = _answer(sa, quality, seg_index)
    TRANSCRIPTS[sa.id] = text
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "answer.wav"
        lead = 6.5 if seg_index in timing.get("delay", set()) else 0.8
        pause = 3.8 if seg_index in timing.get("pause", set()) else 0.0
        # The student speaks the target language; a long pause is real silence between two halves of the answer.
        lang = sa.segment.target_language.code
        lang = "en" if lang == "en" else sa.segment.dialogue.language_pair.lote.code
        words = text.split()
        parts = [" ".join(words[: len(words) // 2]), " ".join(words[len(words) // 2:])] if pause and len(words) > 3 else [text]
        duration = speak(wav, parts, lang, female=seed % 2 == 0, lead=lead, pause=pause)
        if duration is None:  # offline: synthetic tones
            duration = speech_like_wav(wav, _words(text), lead=lead, pause_at=0.5 if pause else None, pause=pause,
                                       pitch=170, seed=seed)
        key = f"recordings/{sa.id}/try1.wav"
        get_storage().put(key, wav.read_bytes(), "audio/wav")
    start = int(utcnow().timestamp() * 1000)
    sa.play_count = sa.record_count = 1
    sa.audio_user, sa.audio_mime, sa.audio_duration_seconds, sa.submitted_at = key, "audio/wav", duration, utcnow()
    sa.timing = {"chime_end_ms": start, "record_start_ms": start + 40}


def load_students(db: Session) -> None:
    password = get_settings().demo_password
    for spec in C.STUDENTS:
        if db.scalar(select(User).where(User.email == spec["email"])):
            continue
        lote = languages.lote_by_code(db, spec["lote"])
        u = User(email=spec["email"], first_name=spec["first"], last_name=spec["last"] + " (DEMO)", role=UserRole.STUDENT,
                 password_hash=hash_password(password), preferred_language_id=lote.id,
                 target_exam_date=(utcnow() + timedelta(days=45)).date())
        status = {"Active": SubscriptionStatus.ACTIVE, "Trial": SubscriptionStatus.TRIAL}.get(spec["access"])
        db.add(u)
        db.flush()
        if status:
            u.subscription_status = status
            if "trial_days" in spec:
                u.access_expires_at = utcnow() + timedelta(days=spec["trial_days"])
            db.add(Subscription(user_id=u.id, source="manual", status="active" if status == SubscriptionStatus.ACTIVE else "trialing",
                                current_period_end=u.access_expires_at, note="DEMO account"))
        db.commit()
        for a, (kind, key, quality) in enumerate(spec["attempts"]):
            if kind == "mock":
                ref = svc.start_mock(db, u, db.scalar(select(MockTest).where(MockTest.key == key)))
            else:
                ref = svc.start_practice(db, u, db.scalar(select(Dialogue).where(Dialogue.key == key)))
            for da in ref.dialogue_attempts:
                for i, sa in enumerate(da.segment_attempts):
                    _record(sa, quality, i, seed=zlib.crc32(f"{spec['email']}-{a}-{i}".encode()))
            svc.submit(db, ref)
            # Hold these jobs back from a running worker: score_pending() scores them here with the demo stand-ins.
            for obj in db.new:
                if isinstance(obj, Job):
                    obj.run_after = utcnow() + timedelta(days=365)
            db.commit()
        log.info("student %s", spec["email"])


def score_pending() -> int:
    """Run the queued scoring jobs with the demo stand-ins (no API calls)."""
    from .services import email as email_service
    from .services.ai import llm
    from .services.scoring import transcribe

    s = get_settings()
    s.stt_provider, s.evaluator_provider = "mock", "mock"
    transcribe.mock_answer = lambda sa: TRANSCRIPTS.get(sa.id, "")
    llm.MockProvider.responder = _demo_evaluator
    email_service.get_provider = lambda db=None: email_service.ConsoleProvider()  # never email example.com addresses
    from .models import JobStatus
    from .services.scoring.pipeline import score_segment_job
    from .services.scoring_jobs import SCORE_SEGMENT

    done = 0
    with SessionLocal() as db:
        held = db.scalars(select(Job).where(Job.kind == SCORE_SEGMENT, Job.status == JobStatus.QUEUED,
                                            Job.run_after > utcnow() + timedelta(days=300))).all()
        for job in held:
            # Claim it first so a running worker never picks it up, then score it here.
            job.status, job.attempts = JobStatus.RUNNING, job.attempts + 1
            db.commit()
            score_segment_job(job.payload)
            job.status, job.finished_at = JobStatus.DONE, utcnow()
            db.commit()
            done += 1
    return done


# ------------------------------------------------------------------ reset

def reset(db: Session) -> None:
    storage = get_storage()
    demo_users = list(db.scalars(select(User.id).where(User.email.like("demo.%@example.com"))))
    demo_dialogues = list(db.scalars(select(Dialogue.id).where(Dialogue.key.like("demo-%"))))
    attempts = select(DialogueAttempt.id).where(
        (DialogueAttempt.user_id.in_(demo_users)) | (DialogueAttempt.dialogue_id.in_(demo_dialogues)))
    for sa_id in db.scalars(select(SegmentAttempt.id).where(SegmentAttempt.dialogue_attempt_id.in_(attempts))):
        storage.delete_prefix(f"recordings/{sa_id}")
    db.execute(delete(DialogueAttempt).where((DialogueAttempt.user_id.in_(demo_users)) | (DialogueAttempt.dialogue_id.in_(demo_dialogues))))
    db.execute(delete(MockTestAttempt).where(MockTestAttempt.user_id.in_(demo_users)))
    for m in db.scalars(select(MockTest).where(MockTest.key.like("demo-%"))):
        db.execute(delete(MockTestAttempt).where(MockTestAttempt.mock_test_id == m.id))
        db.delete(m)
    for d in db.scalars(select(Dialogue).where(Dialogue.key.like("demo-%"))):
        for seg in d.segments:
            storage.delete_prefix(f"media/{seg.id}")
            storage.delete(f"waveforms/{seg.id}.png")
        db.delete(d)
    for c in db.scalars(select(Course).where(Course.key.like("demo-%"))):
        db.delete(c)
    for r in db.scalars(select(Resource).where(Resource.key.like("demo-%"))):
        resource_svc.remove_file(r)
        db.delete(r)
    for uid in demo_users:
        db.delete(db.get(User, uid))
    db.commit()
    log.info("demo data removed")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if get_settings().is_production:
        sys.exit("Refusing to load demo data: ENVIRONMENT is production.")
    with SessionLocal() as db:
        if "--reset" in sys.argv:
            reset(db)
            return
        load_dialogues(db)
        load_courses(db)
        load_hub(db)
        load_students(db)
    scored = score_pending()
    log.info("demo data ready (%s scoring jobs run). Demo students: %s",
             scored, ", ".join(s["email"] for s in C.STUDENTS))


if __name__ == "__main__":
    main()
