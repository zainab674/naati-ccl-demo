"""Deterministic scoring: CCL points, repeat deductions, pass/fail. No AI here."""
from collections import OrderedDict

from sqlalchemy.orm import Session

from ..models import Activity, Attempt
from ..settings import ccl_config, rubric_config


def _half(x: float) -> float:
    return round(x * 2) / 2


def dialogue_groups(attempt: Attempt) -> "OrderedDict[str, list[int]]":
    groups: OrderedDict[str, list[int]] = OrderedDict()
    for idx, item in enumerate(attempt.plan_json):
        groups.setdefault(item["activity_id"], []).append(idx)
    return groups


def repeats_used(attempt: Attempt, indices: list[int]) -> int:
    plays = attempt.plays_json or {}
    return sum(max(0, plays.get(str(i), 0) - 1) for i in indices)


def attempt_results(db: Session, attempt: Attempt, include_raw: bool = False) -> dict:
    cfg = ccl_config()
    cat_names = {c["id"]: c["name"] for c in rubric_config()["categories"]}
    by_index = {r.seg_index: r for r in attempt.responses}
    dialogues = []
    pending = 0

    for activity_id, indices in dialogue_groups(attempt).items():
        activity = db.get(Activity, activity_id)
        n = len(indices)
        scale = (cfg["full_length_segments"] / n) if cfg["scale_deductions_to_full_length"] and n else 1
        reps = repeats_used(attempt, indices)
        extra_reps = max(0, reps - cfg["repeats"]["free_per_dialogue"])
        repeat_points = extra_reps * cfg["repeats"]["deduction_per_extra"]

        segments, raw_total = [], 0.0
        by_cat = {k: 0.0 for k in cat_names}
        for pos, idx in enumerate(indices):
            seg_ref = attempt.plan_json[idx]
            resp = by_index.get(idx)
            seg = next((s for s in activity.segments if s.id == seg_ref["segment_id"]), None)
            entry = {
                "index": idx, "number": pos + 1,
                "speaker": seg.speaker if seg else "",
                "source_text": seg.source_text if seg else "",
                "reference_text": seg.reference_text if seg else "",
                "plays": (attempt.plays_json or {}).get(str(idx), 0),
                "response": None,
            }
            if resp:
                m = resp.effective_marking
                ai = next((x for x in reversed(resp.markings) if x.source == "ai"), None)
                if not m and resp.status != "error":
                    pending += 1
                if m:
                    raw_total += m.points_deducted
                    for issue in m.issues_json:
                        sev = rubric_config()["severity_points"].get(issue.get("severity"), 0)
                        by_cat[issue.get("category", "accuracy")] = by_cat.get(issue.get("category", "accuracy"), 0) + sev
                entry["response"] = {
                    "id": resp.id,
                    "transcript": resp.transcript,
                    "stt_provider": resp.stt_provider,
                    "stt_confidence": resp.stt_confidence,
                    "needs_review": resp.needs_review,
                    "status": resp.status,
                    "error": resp.error,
                    "delivery": resp.delivery_json,
                    "has_audio": bool(resp.audio_key),
                    "marking": _marking_dict(m, include_raw) if m else None,
                    "ai_marking": _marking_dict(ai, include_raw) if (ai and m and m.source == "assessor") else None,
                }
            elif attempt.status != "in_progress":
                raw_total += cfg["unanswered_deduction"]
            segments.append(entry)

        deducted = (raw_total + repeat_points) * scale
        score = max(0.0, _half(cfg["dialogue_max"] - deducted))
        dialogues.append({
            "activity_id": activity_id,
            "title": activity.title,
            "domain": activity.domain,
            "difficulty": activity.difficulty,
            "score": score,
            "max": cfg["dialogue_max"],
            "meets_minimum": score >= cfg["pass_min_per_dialogue"],
            "repeats_used": reps,
            "repeat_deduction": _half(repeat_points * scale),
            "scale": round(scale, 2),
            "by_category": [{"id": k, "name": cat_names[k], "points": _half(v * scale)} for k, v in by_cat.items()],
            "segments": segments,
        })

    total = sum(d["score"] for d in dialogues)
    total_max = sum(d["max"] for d in dialogues)
    if attempt.mode == "mock":
        passed = total >= cfg["pass_total"] and all(d["meets_minimum"] for d in dialogues)
    else:
        passed = all(d["meets_minimum"] for d in dialogues)
    reviewed = any(
        (r.effective_marking and r.effective_marking.source == "assessor") for r in attempt.responses
    )
    return {
        "attempt_id": attempt.id,
        "mode": attempt.mode,
        "status": attempt.status,
        "pending_segments": pending,
        "total": total,
        "total_max": total_max,
        "passed": passed,
        "pass_rules": {"pass_total": cfg["pass_total"], "pass_min_per_dialogue": cfg["pass_min_per_dialogue"]},
        "reviewed_by_assessor": reviewed,
        "started_at": attempt.started_at.isoformat() + "Z",
        "submitted_at": attempt.submitted_at.isoformat() + "Z" if attempt.submitted_at else None,
        "dialogues": dialogues,
    }


def _marking_dict(m, include_raw: bool) -> dict:
    d = {
        "id": m.id, "source": m.source, "marker": m.marker, "issues": m.issues_json,
        "points_deducted": m.points_deducted, "summary": m.summary, "note": m.note,
        "created_at": m.created_at.isoformat() + "Z",
    }
    if include_raw:
        d["raw"] = m.raw_model_json
    return d
