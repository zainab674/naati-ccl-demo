"""Marking pipeline for one interpreted segment.

    transcript -> delivery_issues()      static code: fillers, pauses, self-corrections
               -> accuracy/language issues
                     claude     : one structured-output model call, schema-validated
                     heuristic  : static fallback (numbers + content coverage)
               -> points from rubric severity_points (never from the model)

Only the language judgement uses AI. Everything else is deterministic, which
is the split to show when the client asks "static code or APIs?".
"""
import difflib
import json
import re
import unicodedata

import anthropic
from sqlalchemy.orm import Session

from ..models import Marking, SegmentResponse
from ..settings import ccl_config, get_settings, rubric_config


class MarkingError(Exception):
    pass


# ---------------------------------------------------------------- helpers

def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def _tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFC", s.lower())
    return re.findall(r"[\wऀ-ॿ]+(?:[.,]\d+)?", s)


def _numbers(s: str) -> list[str]:
    return [n.replace(",", "") for n in re.findall(r"\d+(?:[.,]\d+)*", s)]


def points_for(issues: list[dict]) -> float:
    sp = rubric_config()["severity_points"]
    return round(sum(sp.get(i.get("severity", "minor"), 0) for i in issues), 2)


def _valid_pairs() -> set[tuple[str, str]]:
    return {(c["id"], ch["id"]) for c in rubric_config()["categories"] for ch in c["checks"]}


# ---------------------------------------------------------------- wrong language (static)

def wrong_language(transcript: str, target: str, detected: str | None = None) -> bool:
    cfg = rubric_config()["wrong_language"]
    if detected:  # trust the STT provider's own language ID when it gives one
        return detected not in cfg["accepted"].get(target, [target])
    text = _norm_ws(transcript)
    tokens = re.findall(r"[\wऀ-ॿ]+", text.lower())
    if not tokens:
        return False
    deva = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    letters = sum(1 for ch in text if ch.isalpha())
    if target == "en" and letters and deva / letters > 0.3:
        return True
    words = set(cfg["english_in_devanagari"] if target == "hi" else cfg["hindi_in_latin"])
    hits = sum(1 for t in tokens if t in words)
    return hits >= cfg["min_hits"] and hits / len(tokens) >= cfg["min_ratio"]


# ---------------------------------------------------------------- delivery (static)

def delivery_metrics(words: list[dict], transcript: str, language: str) -> dict:
    cfg = rubric_config()["delivery"]
    text = " " + _norm_ws(transcript).lower() + " "
    fillers = [f for f in cfg["fillers"].get(language, [])
               if re.search(rf"(?<![\wऀ-ॿ]){re.escape(f)}(?![\wऀ-ॿ])", text)]
    corrections = [m for m in cfg["self_correction_markers"].get(language, []) if m.lower() in text]
    pauses = []
    for a, b in zip(words, words[1:]):
        gap = (b.get("start") or 0) - (a.get("end") or 0)
        if gap >= cfg["long_pause_seconds"]:
            pauses.append({"after": a["word"].strip(), "seconds": round(gap, 1)})
    latency = round(words[0]["start"], 1) if words else None
    trailing = "..." in transcript or "…" in transcript
    return {"fillers": fillers, "self_corrections": corrections, "long_pauses": pauses,
            "response_latency": latency, "trailing_off": trailing}


def _find_quote(transcript: str, needle: str) -> str:
    """Return the transcript's own spelling of needle (case-insensitive)."""
    m = re.search(re.escape(needle), transcript, flags=re.IGNORECASE)
    return m.group(0) if m else ""


def delivery_issues(metrics: dict, transcript: str) -> list[dict]:
    issues = []
    for f in metrics["fillers"][:2]:
        issues.append({"category": "delivery", "check": "hesitation", "severity": "minor",
                       "quote": _find_quote(transcript, f),
                       "explanation": f'Filler "{f}" breaks the flow. Pause silently instead, or keep going.'})
    for p in metrics["long_pauses"][:2]:
        issues.append({"category": "delivery", "check": "hesitation", "severity": "minor",
                       "quote": _find_quote(transcript, p["after"]),
                       "explanation": f'{p["seconds"]}s pause after "{p["after"]}". Long pauses read as uncertainty.'})
    if metrics["self_corrections"]:
        m = metrics["self_corrections"][0]
        issues.append({"category": "delivery", "check": "self_correction", "severity": "minor",
                       "quote": _find_quote(transcript, m),
                       "explanation": "Self-correction mid-utterance. Correcting is better than leaving an error, but frequent corrections cost marks."})
    if metrics["trailing_off"] and not metrics["fillers"]:
        issues.append({"category": "delivery", "check": "incomplete", "severity": "minor",
                       "quote": "...", "explanation": "The utterance trails off. Finish each sentence cleanly."})
    return [i for i in issues if i["quote"]]


# ---------------------------------------------------------------- heuristic marker (static)

def heuristic_issues(source: str, reference: str, transcript: str) -> tuple[list[dict], str]:
    issues: list[dict] = []
    ref_nums, got_nums = _numbers(reference) or _numbers(source), _numbers(transcript)
    missing = [n for n in ref_nums if n not in got_nums]
    extra = [n for n in got_nums if n not in ref_nums]
    for n in missing:
        if extra:
            wrong = extra.pop(0)
            issues.append({"category": "accuracy", "check": "distortion", "severity": "critical",
                           "quote": _find_quote(transcript, wrong),
                           "explanation": f'You said "{wrong}" but the speaker said "{n}". Numbers must be exact.'})
        else:
            issues.append({"category": "accuracy", "check": "omission", "severity": "major", "quote": "",
                           "explanation": f'The figure "{n}" was not interpreted.'})

    ref_t, got_t = _tokens(reference), _tokens(transcript)
    ratio = difflib.SequenceMatcher(None, ref_t, got_t).ratio() if ref_t else 1.0
    if ratio < 0.45:
        missed = [t for t in ref_t if t not in got_t and not t.isdigit()][:6]
        issues.append({"category": "accuracy", "check": "omission", "severity": "major", "quote": "",
                       "explanation": "Large parts of the segment are missing or changed. Not found: "
                                      + ", ".join(missed)})
    elif len(got_t) > len(ref_t) * 1.5 and len(got_t) - len(ref_t) > 6:
        issues.append({"category": "accuracy", "check": "insertion", "severity": "minor", "quote": "",
                       "explanation": "Your version is much longer than the original. Avoid adding information."})
    summary = f"Static check: {round(ratio * 100)}% content overlap with the reference."
    return issues, summary


# ---------------------------------------------------------------- Claude marker

def _schema() -> dict:
    cats = rubric_config()["categories"]
    return {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": [c["id"] for c in cats if c["id"] != "delivery"]},
                        "check": {"type": "string", "enum": sorted({ch["id"] for c in cats if c["id"] != "delivery" for ch in c["checks"]})},
                        "severity": {"type": "string", "enum": list(rubric_config()["severity_points"])},
                        "quote": {"type": "string"},
                        "explanation": {"type": "string"},
                        "possibly_transcription_error": {"type": "boolean"},
                    },
                    "required": ["category", "check", "severity", "quote", "explanation",
                                 "possibly_transcription_error"],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["issues", "summary", "confidence"],
        "additionalProperties": False,
    }


def _system_prompt() -> str:
    rubric = rubric_config()
    lines = []
    for c in rubric["categories"]:
        if c["id"] == "delivery":
            continue
        lines.append(f'- {c["id"]} ({c["name"]}): {c["description"]}')
        for ch in c["checks"]:
            lines.append(f'    - {ch["id"]}: {ch["description"]}')
    sev = ", ".join(f"{k} = {v} pts" for k, v in rubric["severity_points"].items())
    return f"""You are an experienced NAATI CCL examiner marking one segment of a Hindi and English community interpreting test.

The candidate heard the source segment and interpreted it aloud into the other language. You receive the source, one reference interpretation, and a speech-to-text transcript of what the candidate said.

Identify every issue in these categories:
{chr(10).join(lines)}

Delivery (fillers, pauses, self-corrections) is measured separately by code. Do not report it.

Severity: {sev}. Critical is for errors that would mislead the listener on something important, such as a wrong number, dose, date, amount, negation or who does what. Major is a meaningful omission or distortion of a detail. Minor is a small loss of nuance, wording or register.

How to judge:
- The reference is one acceptable rendering, not the only one. Do not penalise valid synonyms, reordering or natural paraphrase that keeps the meaning.
- Code-mixing common English words into Hindi (appointment, bank, form) is normal and acceptable.
- "quote" must be copied verbatim, character for character, from the candidate transcript. It shows the student exactly where the problem is. For an omission, quote the nearby words where the missing information should have been. Use an empty string only if the transcript is empty.
- "explanation" is written to the student in English: one or two sentences saying what went wrong and what the speaker actually said.
- The transcript comes from speech recognition and may contain recognition errors. If an apparent error looks like a mis-hearing (a near-homophone, garbled word) rather than an interpreting error, set possibly_transcription_error to true and use minor severity.
- If the interpretation is fully accurate, return an empty issues list.
- "summary" is one sentence for the student. "confidence" is 0 to 1: how sure you are of this marking given transcript quality."""


def _claude_issues(source: str, reference: str, transcript: str, src_lang: str, tgt_lang: str) -> tuple[list[dict], str, dict]:
    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key, base_url=s.anthropic_base_url)
    lang = {"en": "English", "hi": "Hindi"}
    user = (f"Source ({lang[src_lang]}):\n{source}\n\n"
            f"Reference interpretation ({lang[tgt_lang]}):\n{reference}\n\n"
            f"Candidate transcript ({lang[tgt_lang]}):\n{transcript}")
    messages = [{"role": "user", "content": user}]
    last_error = ""
    for attempt in range(2):  # one retry on invalid output, then fail visibly
        if last_error:
            messages = [{"role": "user", "content": user + f"\n\nYour previous answer was invalid: {last_error} Fix it."}]
        try:
            resp = client.beta.messages.create(
                model=s.claude_model,
                max_tokens=8000,
                system=_system_prompt(),
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": _schema()}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise MarkingError(f"Model rate limited: {e}") from e
        except anthropic.APIStatusError as e:
            raise MarkingError(f"Model API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise MarkingError(f"Could not reach model API: {e}") from e

        if resp.stop_reason == "refusal":
            raise MarkingError("Model declined to mark this segment.")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            last_error = "Output was not valid JSON."
            continue
        problem = _validate(data.get("issues", []), transcript)
        if problem:
            last_error = problem
            continue
        raw = {"model": resp.model, "output": data, "usage": resp.usage.model_dump() if resp.usage else {}}
        return data["issues"], data.get("summary", ""), raw
    raise MarkingError(f"Model output failed validation twice: {last_error}")


def _validate(issues: list[dict], transcript: str) -> str:
    pairs = _valid_pairs()
    norm_t = _norm_ws(transcript).lower()
    for i, issue in enumerate(issues):
        if (issue.get("category"), issue.get("check")) not in pairs:
            return f'Issue {i}: check "{issue.get("check")}" does not belong to category "{issue.get("category")}".'
        q = _norm_ws(issue.get("quote", "")).lower()
        if q and q not in norm_t:
            return f'Issue {i}: quote "{issue.get("quote")}" is not an exact substring of the candidate transcript.'
    return ""


# ---------------------------------------------------------------- orchestration

def mark_response(db: Session, resp: SegmentResponse) -> Marking:
    seg = resp.segment
    transcript = resp.transcript or ""
    marker = get_settings().resolved_marker
    ccl = ccl_config()

    if not _norm_ws(transcript):
        issues = [{"category": "delivery", "check": "incomplete", "severity": "critical", "quote": "",
                   "explanation": "No interpretation was recorded for this segment."}]
        m = Marking(response_id=resp.id, source="ai", marker="rules", issues_json=issues,
                    points_deducted=ccl["unanswered_deduction"], summary="Segment not answered.")
        db.add(m)
        return m

    detected = (resp.delivery_json or {}).get("detected_language")
    if wrong_language(transcript, seg.target_language, detected):
        lang = {"en": "English", "hi": "Hindi"}
        wrong = lang["en" if seg.target_language == "hi" else "hi"]
        issues = [{"category": "accuracy", "check": "wrong_language", "severity": "critical", "quote": "",
                   "explanation": f"You answered in {wrong}. This segment was spoken in {lang[seg.speaker]} "
                                  f"and had to be interpreted into {lang[seg.target_language]}."}]
        m = Marking(response_id=resp.id, source="ai", marker="rules", issues_json=issues,
                    points_deducted=ccl["unanswered_deduction"], summary="Interpreted into the wrong language.")
        db.add(m)
        return m

    metrics = delivery_metrics(resp.stt_words_json or [], transcript, seg.target_language)
    metrics["detected_language"] = detected
    resp.delivery_json = metrics
    d_issues = delivery_issues(metrics, transcript)

    if marker == "claude":
        a_issues, summary, raw = _claude_issues(seg.source_text, seg.reference_text, transcript,
                                                seg.speaker, seg.target_language)
        marker_name = raw.get("model", get_settings().claude_model)
        confidence = raw["output"].get("confidence")
        if confidence is not None and confidence < ccl["low_confidence_threshold"]:
            resp.needs_review = True
        if any(i.get("possibly_transcription_error") for i in a_issues):
            resp.needs_review = True
    else:
        a_issues, summary = heuristic_issues(seg.source_text, seg.reference_text, transcript)
        raw = {"marker": "heuristic", "note": "Static fallback marker (no model key configured)."}
        marker_name = "heuristic"

    if resp.stt_confidence is not None and resp.stt_confidence < ccl["low_confidence_threshold"]:
        resp.needs_review = True

    issues = a_issues + d_issues
    m = Marking(response_id=resp.id, source="ai", marker=marker_name, issues_json=issues,
                points_deducted=points_for(issues), summary=summary, raw_model_json=raw)
    db.add(m)
    return m
