"""Score every validation recording with the production pipeline (speech-to-text -> timing analysis -> evaluator ->
deduction engine) without writing to the database, keeping each error's Meaning Unit, quote and time so it can be
matched against examiner marks. Results are cached per run key (prompt version, models, scoring config, language
guidance), so the expensive AI calls are made once per configuration."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import select

from app.models import Dialogue, Language, LanguageScoringConfig, LanguageType, Segment
from app.services.scoring import engine
from app.services.scoring.evaluator import PROMPT_VERSION, evaluate
from app.services.scoring.timing import analyse
from app.services.stt import get_stt, normalise_audio
from app.settings import BASE_DIR, get_settings, scoring_config

from .dataset import Dataset
from .metrics import ErrorItem, normalise_text, quote_in_transcript

TIMING_TYPES = {"Pause": "pause", "StartDelay": "start_delay"}
ENGINE_TYPE = {  # validation error type -> (engine criterion, engine enum value)
    "omission": ("accuracy", "Omission"), "distortion": ("accuracy", "Distortion"), "insertion": ("accuracy", "Insertion"),
    "grammar": ("language", "Grammar"), "unidiomatic_usage": ("language", "UnidiomaticUsage"),
    "register": ("language", "Register"), "sentence_structure": ("language", "SentenceStructure"),
    "pronunciation": ("language", "Pronunciation"),
    "pause": ("fluency", "Pause"), "start_delay": ("fluency", "StartDelay"), "hesitation": ("fluency", "Hesitation"),
    "self_correction": ("fluency", "SelfCorrection"),
}


@dataclass
class AIItem:
    type: str
    mu_no: int | None = None
    start: float | None = None
    end: float | None = None
    quote: str = ""
    quote_ok: bool = True
    confidence: float | None = None
    source: str = "evaluator"  # evaluator | timing


@dataclass
class AIRecording:
    recording_id: str
    transcript: str
    speech_start: float | None
    pauses: list[tuple[float, float]]
    items: list[AIItem] = field(default_factory=list)
    deductions: dict[str, float] = field(default_factory=dict)  # criterion -> deduction (brief penalties)
    error: str = ""
    mu_count: int = 0  # active Meaning Units in the segment (for the MU-count adjustment)

    def error_items(self) -> list[ErrorItem]:
        return [ErrorItem(self.recording_id, i.type, i.mu_no, i.start, i.end) for i in self.items]


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def run_key(db, language: str) -> tuple[str, dict]:
    s = get_settings()
    cfg = (BASE_DIR / "config" / "scoring.yaml").read_bytes()
    guidance = db.scalar(select(LanguageScoringConfig).join(Language, Language.id == LanguageScoringConfig.language_id)
                         .where(LanguageScoringConfig.active, Language.code == language))
    parts = {"prompt": PROMPT_VERSION, "evaluator": s.resolved_evaluator, "stt": s.resolved_stt,
             "stt_model": s.stt_model, "gemini_model": s.gemini_model,
             "scoring_yaml_sha": hashlib.sha256(cfg).hexdigest()[:12],
             "guidance_sha": hashlib.sha256(json.dumps(
                 [guidance.grammar_guidelines, guidance.register_guidelines, guidance.hesitation_markers,
                  guidance.ai_prompt_addition] if guidance else [], ensure_ascii=False).encode()).hexdigest()[:12]}
    key = hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]
    return key, parts


def locate(quote: str, words: list[dict]) -> tuple[float | None, float | None]:
    """Time span of a quote in the speech-to-text word timings (first exact token match)."""
    q = normalise_text(quote).split()
    toks = [(normalise_text(w.get("word", "")), w) for w in words]
    toks = [(t, w) for t, w in toks if t]
    if not q:
        return None, None
    flat = [t for t, _ in toks]
    for i in range(len(flat) - len(q) + 1):
        if flat[i:i + len(q)] == q:
            return float(toks[i][1].get("start", 0)), float(toks[i + len(q) - 1][1].get("end", 0))
    return None, None


def _segment(db, dialogue_key: str, segment_no: int) -> Segment:
    d = db.scalar(select(Dialogue).where(Dialogue.key == dialogue_key))
    seg = next((s for s in (d.segments if d else []) if s.segment_number == segment_no and s.active), None)
    if not seg:
        raise LookupError(f"{dialogue_key} segment {segment_no} is not imported (import the dialogue first)")
    return seg


def score_recording(db, ds: Dataset, recording_id: str) -> AIRecording:
    rec = ds.recordings[recording_id]
    seg = _segment(db, rec.dialogue_key, rec.segment_no)
    cfg = scoring_config()
    lang_cfg = db.scalar(select(LanguageScoringConfig).where(
        LanguageScoringConfig.language_id == seg.target_language_id, LanguageScoringConfig.active))
    markers = list(lang_cfg.hesitation_markers) if lang_cfg else []
    if seg.target_language.language_type == LanguageType.ENGLISH:
        markers += cfg["timing"]["english_hesitation_markers"]
    with tempfile.TemporaryDirectory() as tmp:
        flac = normalise_audio(rec.audio_path, Path(tmp) / "a.flac") if rec.audio_path else None
        if flac is None:
            raise LookupError(f"{recording_id}: no audio_path")
        t = get_stt().transcribe(flac, seg.target_language.stt_code or None)
        timing = analyse(flac, t.words, t.text, {}, cfg["timing"], markers)
    ev = evaluate(seg, t.text, timing.filler_candidates, lang_cfg).evaluation
    items: list[AIItem] = []
    for m in ev.meaning_units:
        if m.result != "correct":
            s, e = locate(m.student_interpretation, t.words)
            items.append(AIItem(m.result, m.meaning_unit, s, e, m.student_interpretation,
                                quote_in_transcript(m.student_interpretation, t.text) or m.result == "omission",
                                m.confidence))
    for kind, rows, attr in (("insertion", ev.insertions, "student_text"), (None, ev.language_quality, "student_text"),
                             (None, ev.fluency, "transcript_excerpt")):
        for x in rows:
            quote = getattr(x, attr)
            s, e = locate(quote, t.words)
            items.append(AIItem(kind or x.error, None, s, e, quote, quote_in_transcript(quote, t.text), x.confidence))
    pauses = []
    for ev_t in timing.events:
        typ = TIMING_TYPES[ev_t.type]
        items.append(AIItem(typ, None, ev_t.start, ev_t.start + ev_t.duration, source="timing"))
        if typ == "pause":
            pauses.append((ev_t.start, ev_t.start + ev_t.duration))
    weights = {m.meaning_unit_number: m.weight for m in seg.meaning_units if m.active}
    totals, _ = engine.segment_totals([engine_item(i.type, weights.get(i.mu_no, 1.0)) for i in items], cfg)
    return AIRecording(recording_id, t.text, timing.speech_start, pauses, items,
                       {"accuracy": totals.accuracy, "language": totals.language, "fluency": totals.fluency},
                       mu_count=len(weights))


def engine_item(error_type: str, weight: float = 1.0) -> engine.Item:
    criterion, value = ENGINE_TYPE[error_type]
    return engine.Item(criterion, value, weight if criterion == "accuracy" else 1.0)


def run(db, ds: Dataset, recording_ids: list[str], refresh: bool = False) -> tuple[str, dict, dict[str, AIRecording]]:
    key, parts = run_key(db, ds.language)
    cache = ds.root / "ai_runs" / key
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "run.json").write_text(json.dumps({**parts, "commit": git_commit()}, indent=1))
    out = {}
    for rid in recording_ids:
        path = cache / f"{rid}.json"
        if path.exists() and not refresh:
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["items"] = [AIItem(**i) for i in raw["items"]]
            raw["pauses"] = [tuple(p) for p in raw["pauses"]]
            out[rid] = AIRecording(**raw)
            continue
        try:
            r = score_recording(db, ds, rid)
        except Exception as e:  # noqa: BLE001 - one bad recording must not stop the study; it is reported
            r = AIRecording(rid, "", None, [], error=f"{type(e).__name__}: {e}")
        path.write_text(json.dumps(asdict(r), ensure_ascii=False, indent=1), encoding="utf-8")
        out[rid] = r
        print(f"  scored {rid}{' (error)' if r.error else ''}", file=sys.stderr)
    return key, parts, out
