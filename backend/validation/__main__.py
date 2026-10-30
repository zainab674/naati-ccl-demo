"""Scoring validation study (docs/SCORING_VALIDATION.md). Run from backend/:

    python -m validation tasks fil --audio-base-url URL      Label Studio tasks for examiner marking
    python -m validation import-labelstudio fil export.json [--examiners map.csv]
    python -m validation freeze fil [--share 0.4]            freeze the dev / held-out split (once)
    python -m validation run fil                             score the dev split and report
    python -m validation run fil --split heldout --final --reason "..."   the held-out run (logged)
    python -m validation rasch fil                           many-facet Rasch on the dev split
    python -m validation simulate                            Meaning-Unit-count simulation
    python -m validation check                               CI: gate entries still backed by passing reports
    python -m validation approve fil --by "Name, date"       add a language to the gate (held-out report must pass)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _db():
    from app.db import SessionLocal
    return SessionLocal()


def cmd_tasks(a):
    from . import dataset, label_studio
    ds = dataset.load(a.language)
    with _db() as db:
        out = label_studio.tasks(db, ds, a.audio_base_url)
    path = ds.root / "label_studio_tasks.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} tasks -> {path}\nLabeling config: {label_studio.CONFIG_PATH}")


def cmd_import(a):
    from . import dataset, label_studio
    examiners = {}
    if a.examiners:
        examiners = {r["label_studio_user"]: r["examiner_id"] for r in csv.DictReader(a.examiners.read_text().splitlines())}
    rows = label_studio.convert(label_studio.load_export(a.export), examiners)
    path = dataset.data_root() / a.language / "annotations.csv"
    label_studio.write_annotations(rows, path)
    print(f"{len(rows)} marks -> {path}")


def cmd_freeze(a):
    from . import dataset, split
    doc = split.freeze(dataset.load(a.language), a.share)
    print(f"Frozen: {len(doc['held_out_recordings'])} held-out recordings from {len(doc['held_out_students'])} students "
          f"(sha256 {doc['held_out_sha256'][:12]}). Do not look at held-out results until the final run.")


def cmd_run(a):
    from . import ai_runs, dataset, report, split
    if a.split == "heldout" and not (a.final and a.reason):
        sys.exit("The held-out set is scored once, for the final result: add --final --reason \"why now\". "
                 "Tune on the dev split only.")
    ds = dataset.load(a.language)
    ids = split.recordings_for(ds, a.split)
    with _db() as db:
        key, parts, ai = ai_runs.run(db, ds, ids, refresh=a.refresh)
    run = {**parts, "key": key, "commit": ai_runs.git_commit()}
    rep = report.build(ds, ai, ids, a.split, run, n_boot=a.boot)
    out = ds.root / "reports"
    out.mkdir(exist_ok=True)
    stem = f"{a.split}-{key}"
    (out / f"{stem}.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / f"{stem}.md").write_text(report.to_markdown(rep), encoding="utf-8")
    print(report.to_markdown(rep))
    if a.split == "heldout":
        n = split.log_heldout_run(ds, a.reason, run, rep["bar"])
        if n > 1:
            print(f"\nNOTE: this is held-out run number {n}. Report it: earlier held-out results may have influenced "
                  "changes since.", file=sys.stderr)
        from .gate import report_path
        report_path(a.language).parent.mkdir(parents=True, exist_ok=True)
        # Committed copy: aggregate numbers only (no transcripts or audio); the per-run files stay in the data dir.
        report_path(a.language).write_text(json.dumps({**rep, "heldout_run_number": n}, indent=1, default=str),
                                           encoding="utf-8")
        report_path(a.language).with_suffix(".md").write_text(report.to_markdown(rep), encoding="utf-8")
        print(f"\nCommitted-report copy: {report_path(a.language)}")


def cmd_rasch(a):
    from app.models import Dialogue
    from sqlalchemy import select

    from . import ai_runs, dataset, rasch, split
    ds = dataset.load(a.language)
    ids = split.recordings_for(ds, a.split)
    with _db() as db:
        _, _, ai = ai_runs.run(db, ds, ids)
        mus = {}
        for key in {r.dialogue_key for r in ds.recordings.values()}:
            d = db.scalar(select(Dialogue).where(Dialogue.key == key))
            for s in (d.segments if d else []):
                if s.active:
                    mus[(key, s.segment_number)] = [m.meaning_unit_number for m in s.meaning_units if m.active]
    obs = rasch.observations(ds, ai, mus, ids)
    f = rasch.fit(obs)
    out = ds.root / "reports" / f"rasch-{a.split}"
    files = rasch.export(obs, out)
    (out / "rasch.md").write_text(rasch.to_markdown(f), encoding="utf-8")
    print(rasch.to_markdown(f))
    print("\nExports for FACETS / R TAM: " + ", ".join(str(p) for p in files))


def cmd_simulate(a):
    from . import simulate_mu_count
    print(simulate_mu_count.to_markdown(simulate_mu_count.table()))


def cmd_check(a):
    from . import gate
    problems = gate.check()
    langs = list(gate.read_gate())
    if problems:
        print("Scoring gate check FAILED:\n" + "\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    none = "no language is validated yet; students see practice feedback without scores"
    print(f"Scoring gate OK: {', '.join(langs) if langs else none}")


def cmd_approve(a):
    from . import gate
    entry = gate.approve(a.language, a.by)
    print(f"{a.language} added to {gate.GATE_PATH}: {entry}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m validation", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tasks")
    t.add_argument("language")
    t.add_argument("--audio-base-url", required=True)
    t.set_defaults(fn=cmd_tasks)
    i = sub.add_parser("import-labelstudio")
    i.add_argument("language")
    i.add_argument("export", type=Path)
    i.add_argument("--examiners", type=Path, help="CSV label_studio_user,examiner_id (pseudonyms)")
    i.set_defaults(fn=cmd_import)
    f = sub.add_parser("freeze")
    f.add_argument("language")
    f.add_argument("--share", type=float, default=0.4)
    f.set_defaults(fn=cmd_freeze)
    r = sub.add_parser("run")
    r.add_argument("language")
    r.add_argument("--split", choices=["dev", "heldout"], default="dev")
    r.add_argument("--final", action="store_true")
    r.add_argument("--reason", default="")
    r.add_argument("--refresh", action="store_true", help="re-score even if this configuration was scored before")
    r.add_argument("--boot", type=int, default=2000)
    r.set_defaults(fn=cmd_run)
    ra = sub.add_parser("rasch")
    ra.add_argument("language")
    ra.add_argument("--split", choices=["dev"], default="dev")
    ra.set_defaults(fn=cmd_rasch)
    sub.add_parser("simulate").set_defaults(fn=cmd_simulate)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    ap = sub.add_parser("approve")
    ap.add_argument("language")
    ap.add_argument("--by", required=True)
    ap.set_defaults(fn=cmd_approve)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
