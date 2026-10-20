"use client";

import { AlertTriangle, ChevronDown, CircleCheck, CircleX } from "lucide-react";
import { type ReactNode, useState } from "react";

import { LABELS, type SegmentResult } from "@/lib/results";
import { Badge, Card, cx } from "./ui";

export function fmtDed(n: number) {
  return n ? `−${Number(n.toFixed(2))}` : "0";
}

function Row({ label, tone, deduction, children, extra }: { label: string; tone: "red" | "amber" | "slate" | "green"; deduction: number; children: ReactNode; extra?: ReactNode }) {
  return (
    <li className="flex gap-3 py-3">
      <div className="w-36 shrink-0"><Badge tone={tone}>{label}</Badge></div>
      <div className="min-w-0 flex-1 space-y-1 text-sm">{children}{extra}</div>
      <div className={cx("w-12 shrink-0 text-right text-sm font-semibold tabular-nums", deduction ? "text-rose-700" : "text-slate-400")}>{fmtDed(deduction)}</div>
    </li>
  );
}

/** One segment's feedback. `actions` lets the admin screen add override controls per item. */
export default function SegmentResultCard({ seg, recordingUrl, defaultOpen, actions }:
  { seg: SegmentResult; recordingUrl?: string; defaultOpen?: boolean; actions?: (kind: string, item: { id: string; deduction: number }) => ReactNode }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const errors = seg.accuracy.filter((a) => a.result !== "Correct").length + seg.insertions.length + seg.language.length + seg.fluency.length;
  return (
    <Card className="overflow-hidden">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-5 py-3 text-left">
        <span className="w-8 font-semibold tabular-nums text-slate-400">{seg.number}</span>
        <Badge>{seg.direction}</Badge>
        <span dir="auto" className="flex-1 truncate text-sm text-slate-600">{seg.skipped ? "Not answered" : seg.transcript || "(no speech recognised)"}</span>
        {seg.needs_review && !seg.reviewed && <Badge tone="amber">Under review</Badge>}
        {seg.reviewed && <Badge tone="violet">Reviewed by a teacher</Badge>}
        <span className="text-xs text-slate-500">{errors} issue{errors === 1 ? "" : "s"}</span>
        <span className={cx("w-12 text-right text-sm font-semibold tabular-nums", seg.deductions.total ? "text-rose-700" : "text-emerald-700")}>{fmtDed(seg.deductions.total)}</span>
        <ChevronDown className={cx("size-4 text-slate-400 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-5 border-t border-slate-100 px-5 py-5">
          <div className="grid gap-4 md:grid-cols-2">
            {seg.source_transcript !== null && (
              <div><div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source ({seg.source_language})</div>
                <p dir="auto" className="mt-1 text-sm">{seg.source_transcript}</p></div>
            )}
            <div><div className="text-xs font-semibold uppercase tracking-wide text-slate-500">What we heard ({seg.target_language})</div>
              <p dir="auto" className="mt-1 text-sm">{seg.skipped ? <i className="text-slate-500">You did not answer this segment.</i> : seg.transcript || <i className="text-slate-500">No speech was recognised.</i>}</p>
              {recordingUrl && seg.has_recording && <audio controls preload="none" src={recordingUrl} className="mt-2 h-9 w-full" controlsList="nodownload" />}
            </div>
          </div>
          {seg.feedback && <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700">{seg.feedback}</p>}
          {seg.scoring_status === "Failed" && <p className="flex items-center gap-2 text-sm text-amber-800"><AlertTriangle className="size-4" /> This segment could not be scored automatically. A teacher will review it.</p>}

          <Section title="Accuracy and completeness" total={seg.deductions.accuracy}>
            {seg.accuracy.map((a) => (
              <Row key={a.id} label={`MU ${a.meaning_unit} · ${LABELS[a.result]}`} deduction={a.deduction}
                tone={a.result === "Correct" ? "green" : "red"} extra={actions?.("accuracy", a)}>
                <div className="flex items-start gap-1.5">{a.result === "Correct" ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" /> : <CircleX className="mt-0.5 size-4 shrink-0 text-rose-600" />}<bdi className="font-medium">{a.source_meaning}</bdi></div>
                {a.student_meaning && <div className="text-slate-600">You said: &ldquo;<bdi>{a.student_meaning}</bdi>&rdquo;</div>}
                {a.result !== "Correct" && a.explanation && <div className="text-slate-600">{a.explanation}</div>}
                {a.result !== "Correct" && a.suggested_version && <div className="text-emerald-800">Suggested: &ldquo;<bdi>{a.suggested_version}</bdi>&rdquo;</div>}
              </Row>
            ))}
            {seg.insertions.map((a) => (
              <Row key={a.id} label="Insertion" tone="red" deduction={a.deduction} extra={actions?.("accuracy", a)}>
                <div>Added: &ldquo;<bdi>{a.student_meaning}</bdi>&rdquo;</div><div className="text-slate-600">{a.explanation}</div>
              </Row>
            ))}
          </Section>

          <Section title="Language quality" total={seg.deductions.language} empty="No language quality issues found.">
            {seg.language.map((e) => (
              <Row key={e.id} label={LABELS[e.type] ?? e.type} tone={e.type === "Pronunciation" ? "slate" : "amber"} deduction={e.deduction} extra={actions?.("language", e)}>
                {e.student_text && <div>&ldquo;<bdi>{e.student_text}</bdi>&rdquo;</div>}
                <div className="text-slate-600">{e.explanation}</div>
                {e.suggested_version && <div className="text-emerald-800">Suggested: &ldquo;<bdi>{e.suggested_version}</bdi>&rdquo;</div>}
                {e.type === "Pronunciation" && e.needs_review && <div className="text-xs text-slate-500">Flagged for a teacher to check; not deducted automatically.</div>}
              </Row>
            ))}
          </Section>

          <Section title="Fluency" total={seg.deductions.fluency} empty="No fluency issues found.">
            {seg.fluency.map((e) => (
              <Row key={e.id} label={LABELS[e.type] ?? e.type} tone="amber" deduction={e.deduction} extra={actions?.("fluency", e)}>
                {e.transcript_excerpt && <div>&ldquo;<bdi>{e.transcript_excerpt}</bdi>&rdquo;</div>}
                <div className="text-slate-600">{e.explanation}</div>
                {e.detection_method === "AudioAnalysis" && <div className="text-xs text-slate-500">Measured from your recording{e.timestamp_seconds !== null ? ` at ${e.timestamp_seconds.toFixed(1)} s` : ""}.</div>}
              </Row>
            ))}
          </Section>
        </div>
      )}
    </Card>
  );
}

function Section({ title, total, children, empty }: { title: string; total: number; children: ReactNode; empty?: string }) {
  const items = Array.isArray(children) ? children.flat().filter(Boolean) : children ? [children] : [];
  return (
    <div>
      <div className="flex items-center justify-between border-b border-slate-100 pb-1">
        <h4 className="text-sm font-semibold">{title}</h4>
        <span className={cx("text-sm font-semibold tabular-nums", total ? "text-rose-700" : "text-slate-400")}>{fmtDed(total)}</span>
      </div>
      {items.length ? <ul className="divide-y divide-slate-50">{children}</ul> : <p className="py-3 text-sm text-slate-500">{empty}</p>}
    </div>
  );
}
