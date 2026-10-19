"""dialogues.csv: one row per Meaning Unit; dialogue and segment columns repeat (format in docs/MVP_SPEC.md).

validate() builds the dry-run report. commit() upserts by dialogue_key / segment_no / mu_no, so re-importing a file
updates in place and never duplicates. Segments or Meaning Units missing from a re-import are deactivated, not
deleted, because past attempts reference them.
"""
import re
from collections import OrderedDict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import (ContentStatus, Dialogue, Difficulty, Direction, MeaningUnit, Segment,
                       Topic)
from ...settings import scoring_config
from ..languages import english, get_or_create_pair, lotes_by_code
from .common import Report, check_urls, parse_bool, read_csv, valid_url

REQUIRED = ["dialogue_key", "dialogue_title", "topic", "difficulty", "lote_language", "segment_no", "direction",
            "audio_url", "transcript", "mu_no", "meaning"]
OPTIONAL = ["description", "instructions", "speaker_label", "speaker_role", "waveform_url",
            "reference_interpretation", "mu_weight", "is_free"]
DIALOGUE_FIELDS = ["dialogue_title", "topic", "difficulty", "lote_language", "description", "instructions", "is_free"]
SEGMENT_FIELDS = ["direction", "speaker_label", "speaker_role", "audio_url", "waveform_url", "transcript"]
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,118}$")


@dataclass
class MU:
    number: int
    meaning: str
    reference: str
    weight: float


@dataclass
class Seg:
    number: int
    direction: Direction
    speaker_label: str
    speaker_role: str
    audio_url: str
    waveform_url: str
    transcript: str
    mus: dict[int, MU] = field(default_factory=dict)


@dataclass
class Dlg:
    key: str
    title: str
    topic: str
    difficulty: Difficulty
    lote_code: str
    description: str
    instructions: str
    is_free: bool | None
    segments: dict[int, Seg] = field(default_factory=OrderedDict)


def _int(value: str) -> int | None:
    try:
        n = int(value)
    except ValueError:
        return None
    return n if n > 0 else None


def parse(db: Session, data: bytes, check_remote: bool = True) -> tuple[Report, list[Dlg]]:
    report = Report()
    rows = read_csv(data, REQUIRED, OPTIONAL)
    if rows[0].get("_unknown_columns"):
        report.warn(1, ",".join(rows[0]["_unknown_columns"]), "Unknown column(s) will be ignored")

    lotes = lotes_by_code(db)
    topics = {t.name.lower() for t in db.scalars(select(Topic))}
    difficulties = {d.value.lower(): d for d in Difficulty}
    directions = {d.value: d for d in Direction}

    dialogues: dict[str, Dlg] = OrderedDict()
    first_dialogue_row: dict[str, dict] = {}
    first_segment_row: dict[tuple[str, int], dict] = {}
    seen_mu: dict[tuple[str, int, int], int] = {}
    urls: dict[str, list[tuple[int, str]]] = {}

    for row in rows:
        r = row["_row"]
        bad = False
        for col in REQUIRED:
            if not row.get(col):
                report.error(r, col, "Required value is missing")
                bad = True
        if bad:
            continue
        key = row["dialogue_key"].lower()
        if not KEY_RE.match(key):
            report.error(r, "dialogue_key", "Use lowercase letters, numbers, - or _ (2-120 characters)")
            continue
        difficulty = difficulties.get(row["difficulty"].lower())
        if not difficulty:
            report.error(r, "difficulty", f"'{row['difficulty']}' is not one of Easy, Intermediate, Difficult")
        lote_code = row["lote_language"].lower()
        if lote_code not in lotes:
            report.error(r, "lote_language", f"Unknown language code '{row['lote_language']}' "
                                             f"(available: {', '.join(sorted(lotes)) or 'none'})")
        direction = directions.get(row["direction"].upper().replace(" ", ""))
        if not direction:
            report.error(r, "direction", f"'{row['direction']}' must be EN>LOTE or LOTE>EN")
        seg_no, mu_no = _int(row["segment_no"]), _int(row["mu_no"])
        if seg_no is None:
            report.error(r, "segment_no", "Must be a whole number from 1")
        if mu_no is None:
            report.error(r, "mu_no", "Must be a whole number from 1")
        weight = 1.0
        if row.get("mu_weight"):
            try:
                weight = float(row["mu_weight"])
                if weight <= 0:
                    raise ValueError
            except ValueError:
                report.error(r, "mu_weight", "Must be a positive number")
        is_free = None
        if row.get("is_free"):
            try:
                is_free = parse_bool(row["is_free"])
            except ValueError:
                report.error(r, "is_free", "Use true/false")
        for col in ("audio_url", "waveform_url"):
            if row.get(col):
                if not valid_url(row[col]):
                    report.error(r, col, "Not a valid http(s) URL")
                else:
                    urls.setdefault(row[col], []).append((r, col))
                    if row[col].startswith("http://"):
                        report.warn(r, col, "URL is not https")
        if not (difficulty and lote_code in lotes and direction and seg_no and mu_no):
            continue

        # Dialogue-level values must agree across all rows of the same dialogue_key.
        if key not in dialogues:
            dialogues[key] = Dlg(key=key, title=row["dialogue_title"], topic=row["topic"], difficulty=difficulty,
                                 lote_code=lote_code, description=row.get("description", ""),
                                 instructions=row.get("instructions", ""), is_free=is_free)
            first_dialogue_row[key] = row
            if row["topic"].lower() not in topics:
                report.warn(r, "topic", f"New topic '{row['topic']}' will be created")
                topics.add(row["topic"].lower())
        else:
            first = first_dialogue_row[key]
            for col in DIALOGUE_FIELDS:
                if row.get(col, "") and row.get(col, "") != first.get(col, ""):
                    report.error(r, col, f"Differs from row {first['_row']} for the same dialogue_key")
        dlg = dialogues[key]

        seg = dlg.segments.get(seg_no)
        if not seg:
            seg = Seg(number=seg_no, direction=direction, speaker_label=row.get("speaker_label", ""),
                      speaker_role=row.get("speaker_role", ""), audio_url=row["audio_url"],
                      waveform_url=row.get("waveform_url", ""), transcript=row["transcript"])
            dlg.segments[seg_no] = seg
            first_segment_row[(key, seg_no)] = row
        else:
            first = first_segment_row[(key, seg_no)]
            for col in SEGMENT_FIELDS:
                if row.get(col, "") and row.get(col, "") != first.get(col, ""):
                    report.error(r, col, f"Differs from row {first['_row']} for the same segment")

        mu_key = (key, seg_no, mu_no)
        if mu_key in seen_mu:
            report.error(r, "mu_no", f"Duplicate dialogue_key/segment_no/mu_no (also row {seen_mu[mu_key]})")
            continue
        seen_mu[mu_key] = r
        seg.mus[mu_no] = MU(number=mu_no, meaning=row["meaning"], reference=row.get("reference_interpretation", ""),
                            weight=weight)

    # Structure checks per dialogue.
    max_score = scoring_config()["dialogue_max"]
    for dlg in dialogues.values():
        numbers = sorted(dlg.segments)
        if numbers != list(range(1, len(numbers) + 1)):
            report.warn(None, "segment_no", f"{dlg.key}: segment numbers are not 1..{len(numbers)} ({numbers})")
        for seg in dlg.segments.values():
            mus = sorted(seg.mus)
            if mus != list(range(1, len(mus) + 1)):
                report.warn(None, "mu_no", f"{dlg.key} segment {seg.number}: meaning units are not 1..{len(mus)}")
        directions_used = {s.direction for s in dlg.segments.values()}
        if len(directions_used) < 2:
            report.warn(None, "direction", f"{dlg.key}: every segment goes the same direction")
        total_mu = sum(len(s.mus) for s in dlg.segments.values())
        if total_mu < max_score * 0.5:
            report.warn(None, "mu_no", f"{dlg.key}: only {total_mu} meaning units for a dialogue marked out of "
                                       f"{max_score:g}")

    if check_remote and urls:
        for url, reason in check_urls(set(urls)).items():
            if reason:
                for r, col in urls[url]:
                    report.error(r, col, f"URL is not reachable ({reason})")

    existing = set(db.scalars(select(Dialogue.key).where(Dialogue.key.in_(list(dialogues)))))
    report.summary = {
        "rows": len(rows),
        "dialogues": len(dialogues),
        "new_dialogues": len([k for k in dialogues if k not in existing]),
        "updated_dialogues": len([k for k in dialogues if k in existing]),
        "segments": sum(len(d.segments) for d in dialogues.values()),
        "meaning_units": sum(len(s.mus) for d in dialogues.values() for s in d.segments.values()),
        "urls_checked": len(urls) if check_remote else 0,
    }
    return report, list(dialogues.values())


def _set(obj, changes: list, **values) -> None:
    for k, v in values.items():
        if getattr(obj, k) != v:
            setattr(obj, k, v)
            changes.append(k)


def commit(db: Session, dialogues: list[Dlg], created_by=None) -> dict:
    """Upsert parsed dialogues. Returns counts and the ids of segments whose audio must be (re)processed."""
    en = english(db)
    lotes = lotes_by_code(db)
    topics = {t.name.lower(): t for t in db.scalars(select(Topic))}
    counts = {"dialogues_created": 0, "dialogues_updated": 0, "segments_created": 0, "segments_updated": 0,
              "segments_deactivated": 0, "meaning_units_created": 0, "meaning_units_updated": 0,
              "meaning_units_deactivated": 0}
    media_segment_ids: list[str] = []
    cfg = scoring_config()

    for d in dialogues:
        lote = lotes[d.lote_code]
        pair = get_or_create_pair(db, en, lote)
        topic = topics.get(d.topic.lower())
        if not topic:
            topic = Topic(name=d.topic, sort_order=len(topics))
            db.add(topic)
            db.flush()
            topics[d.topic.lower()] = topic

        dialogue = db.scalar(select(Dialogue).where(Dialogue.key == d.key))
        changes: list[str] = []
        if not dialogue:
            dialogue = Dialogue(key=d.key, title=d.title, language_pair_id=pair.id, status=ContentStatus.DRAFT,
                                maximum_score=cfg["dialogue_max"], passing_score=cfg["pass_min_per_dialogue"],
                                created_by=created_by, is_free=bool(d.is_free))
            db.add(dialogue)
            db.flush()
            counts["dialogues_created"] += 1
            is_new = True
        else:
            is_new = False
        _set(dialogue, changes, title=d.title, topic_id=topic.id, language_pair_id=pair.id, difficulty=d.difficulty,
             description=d.description, instructions=d.instructions)
        if d.is_free is not None:
            _set(dialogue, changes, is_free=d.is_free)

        existing = {s.segment_number: s for s in dialogue.segments}
        seg_changed = False
        for s in d.segments.values():
            src, tgt = (en, lote) if s.direction == Direction.EN_TO_LOTE else (lote, en)
            seg = existing.get(s.number)
            seg_changes: list[str] = []
            if not seg:
                seg = Segment(dialogue_id=dialogue.id, segment_number=s.number, source_language_id=src.id,
                              target_language_id=tgt.id, source_audio_url=s.audio_url)
                db.add(seg)
                dialogue.segments.append(seg)
                counts["segments_created"] += 1
                seg_changes.append("new")
            _set(seg, seg_changes, source_language_id=src.id, target_language_id=tgt.id, transcript=s.transcript,
                 speaker_label=s.speaker_label, speaker_role=s.speaker_role, active=True,
                 word_count=len(s.transcript.split()))
            if seg.source_audio_url != s.audio_url:
                seg.source_audio_url = s.audio_url
                seg.source_audio_hash = ""
                seg_changes.append("audio")
            if seg.waveform_source_url != s.waveform_url:
                seg.waveform_source_url = s.waveform_url
                seg_changes.append("waveform")
            # (Re)process media when a URL changed or an earlier ingest never finished.
            if "audio" in seg_changes or "waveform" in seg_changes or seg.media_status != "ready":
                seg.media_status = "pending"
            db.flush()
            if seg.media_status == "pending":
                media_segment_ids.append(str(seg.id))

            mus = {m.meaning_unit_number: m for m in seg.meaning_units}
            for m in s.mus.values():
                mu = mus.get(m.number)
                if not mu:
                    mu = MeaningUnit(segment_id=seg.id, meaning_unit_number=m.number, meaning=m.meaning)
                    db.add(mu)
                    seg.meaning_units.append(mu)
                    counts["meaning_units_created"] += 1
                    seg_changes.append("mu")
                mu_changes: list[str] = []
                _set(mu, mu_changes, meaning=m.meaning, reference_interpretation=m.reference, weight=m.weight,
                     reference_language_id=tgt.id, active=True)
                if mu_changes and m.number in mus:
                    counts["meaning_units_updated"] += 1
                    seg_changes.append("mu")
            for number, mu in mus.items():
                if number not in s.mus and mu.active:
                    mu.active = False
                    counts["meaning_units_deactivated"] += 1
                    seg_changes.append("mu")
            if seg_changes and "new" not in seg_changes:
                counts["segments_updated"] += 1
            seg_changed = seg_changed or bool(seg_changes)

        for number, seg in existing.items():
            if number not in d.segments and seg.active:
                seg.active = False
                counts["segments_deactivated"] += 1
                seg_changed = True

        if not is_new and (changes or seg_changed):
            counts["dialogues_updated"] += 1
            dialogue.version += 1  # attempts record dialogue_version, so old results stay explainable
    db.commit()
    counts["media_segment_ids"] = media_segment_ids
    return counts
