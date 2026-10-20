"""Build content directly in the database for tests (skips CSV import and media processing)."""
from sqlalchemy import select

from app.models import (ContentStatus, Course, Dialogue, Language, LanguagePair, Lesson, MeaningUnit, MockTest,
                        MockTestDialogue, Segment, Topic)
from app.services.storage import get_storage

FAKE_PLAYLIST = ("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:0\n"
                 '#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-KEY:METHOD=AES-128,URI="__KEY_URI__",IV=0x00000000000000000000000000000001\n'
                 "#EXTINF:4.0,\ns000.ts\n#EXT-X-ENDLIST\n")


def make_dialogue(db, key="dlg-1", segments=3, mus_per_segment=2, status=ContentStatus.PUBLISHED, is_free=False,
                  title=None, topic="Health", lote="fil"):
    en = db.scalar(select(Language).where(Language.code == "en"))
    fil = db.scalar(select(Language).where(Language.code == lote))
    pair = db.scalar(select(LanguagePair).where(LanguagePair.lote_language_id == fil.id))
    t = db.scalar(select(Topic).where(Topic.name == topic))
    d = Dialogue(key=key, title=title or key.replace("-", " ").title(), topic_id=t.id, language_pair_id=pair.id,
                 status=status, is_free=is_free, description="Test dialogue")
    db.add(d)
    db.flush()
    storage = get_storage()
    for n in range(1, segments + 1):
        src, tgt = (en, fil) if n % 2 else (fil, en)
        seg = Segment(dialogue_id=d.id, segment_number=n, source_language_id=src.id, target_language_id=tgt.id,
                      transcript=f"Source transcript {n}", source_audio_url=f"https://cdn.example.com/ok/{key}-{n}.mp3",
                      media_status="ready", duration_seconds=4.0, speaker_label="Speaker",
                      speaker_role="Receptionist" if n % 2 else "Client")
        db.add(seg)
        db.flush()
        prefix = f"media/{seg.id}/test"
        storage.put(f"{prefix}/index.m3u8", FAKE_PLAYLIST.encode())
        storage.put(f"{prefix}/enc.key", b"0123456789abcdef")
        storage.put(f"{prefix}/s000.ts", b"\x47" * 188)
        storage.put(f"waveforms/{seg.id}.png", b"\x89PNG\r\n\x1a\nfake")
        seg.audio_file, seg.waveform_image = prefix, f"waveforms/{seg.id}.png"
        for m in range(1, mus_per_segment + 1):
            db.add(MeaningUnit(segment_id=seg.id, meaning_unit_number=m, meaning=f"Meaning {n}.{m}",
                               reference_interpretation=f"Reference {n}.{m}", reference_language_id=tgt.id))
    db.commit()
    db.refresh(d)
    return d


def make_mock(db, dialogues, key="mock-1", status=ContentStatus.PUBLISHED, is_free=False):
    m = MockTest(key=key, title=key.replace("-", " ").title(), language_pair_id=dialogues[0].language_pair_id,
                 status=status, is_free=is_free)
    db.add(m)
    db.flush()
    for pos, d in enumerate(dialogues, start=1):
        db.add(MockTestDialogue(mock_test_id=m.id, dialogue_id=d.id, position=pos))
    db.commit()
    db.refresh(m)
    return m


def make_course(db, key="intro", lessons=2, free_lessons=1, status=ContentStatus.PUBLISHED):
    c = Course(key=key, title=key.title(), description="Course", status=status)
    db.add(c)
    db.flush()
    for n in range(1, lessons + 1):
        db.add(Lesson(course_id=c.id, lesson_number=n, title=f"Lesson {n}", html_content=f"<p>Lesson {n}</p>",
                      video_url="https://www.youtube.com/embed/x", is_free=n <= free_lessons))
    db.commit()
    db.refresh(c)
    return c
