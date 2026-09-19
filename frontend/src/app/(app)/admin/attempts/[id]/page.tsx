"use client";

import { ArrowLeft, Code2, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import SegmentFeedback from "@/components/SegmentFeedback";
import { Badge, Button, Card, ErrorNote, ScoreRing, Spinner } from "@/components/ui";
import { api, fmtDateTime, type Issue, type Results, type SegmentResult } from "@/lib/api";

type Rubric = { categories: { id: string; name: string; checks: { id: string }[] }[]; severity_points: Record<string, number> };
type Detail = Results & {
  student: { name: string; email: string; flagged: boolean };
  integrity_events: { type: string; index: number; at: string; detail?: string }[];
  rubric: Rubric;
};

export default function AdminAttempt() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  useEffect(() => { api<Detail>(`/admin/attempts/${id}`).then(setD); }, [id]);
  if (!d) return <Spinner />;

  const onSaved = (r: Results) => setD({ ...d, ...r });

  return (
    <div className="space-y-6">
      <Link href="/admin" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-ink"><ArrowLeft className="size-4" /> Submissions</Link>
      <Card className="flex flex-wrap items-center gap-8 p-6">
        <ScoreRing score={d.total} max={d.total_max} passed={d.passed} size={112} />
        <div className="flex-1">
          <div className="flex flex-wrap gap-2">
            <Badge tone={d.mode === "mock" ? "violet" : "brand"}>{d.mode}</Badge>
            <Badge tone={d.passed ? "green" : "red"}>{d.passed ? "pass" : "fail"}</Badge>
            {d.student.flagged && <Badge tone="red">account flagged</Badge>}
          </div>
          <h1 className="mt-2 text-xl font-semibold">{d.student.name}</h1>
          <p className="text-sm text-slate-500">{d.student.email} · {d.dialogues.map((x) => `${x.title} ${x.score}/45`).join(" · ")}</p>
        </div>
        <div className="min-w-56 text-sm">
          <div className="mb-1 font-medium">Integrity log</div>
          {d.integrity_events.length === 0 ? <div className="text-slate-400">No events</div> : (
            <ul className="max-h-28 space-y-0.5 overflow-auto text-xs text-slate-600">
              {d.integrity_events.map((e, i) => (
                <li key={i}><span className="text-slate-400">{fmtDateTime(e.at)}</span> · {e.type.replace("_", " ")} at segment {e.index + 1}</li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      {d.dialogues.map((dl, di) => (
        <Card key={dl.activity_id}>
          <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Dialogue {di + 1}</div>
              <h2 className="font-semibold">{dl.title}</h2>
            </div>
            <div className="text-right text-sm">
              <div className="text-xl font-semibold tabular-nums">{dl.score}/45</div>
              <div className="text-xs text-slate-500">{dl.repeats_used} repeats · scale ×{dl.scale}</div>
            </div>
          </div>
          <div className="divide-y divide-slate-100">
            {dl.segments.map((s) => <SegmentReview key={s.index} seg={s} attemptId={d.attempt_id} rubric={d.rubric} onSaved={onSaved} />)}
          </div>
        </Card>
      ))}
    </div>
  );
}

function SegmentReview({ seg, attemptId, rubric, onSaved }: { seg: SegmentResult; attemptId: string; rubric: Rubric; onSaved: (r: Results) => void }) {
  const [editing, setEditing] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const r = seg.response;
  const aiMarking = r?.ai_marking ?? r?.marking;
  return (
    <div className="px-6 py-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold">Segment {seg.number}</span>
          <span className="text-slate-400">{seg.speaker === "en" ? "EN → HI" : "HI → EN"} · played {seg.plays}×</span>
          {r?.needs_review && <Badge tone="amber">needs review</Badge>}
          {r?.stt_confidence != null && <span className="text-xs text-slate-400">STT confidence {Math.round(r.stt_confidence * 100)}%</span>}
        </div>
        {r && (
          <div className="flex gap-2">
            {aiMarking?.raw && <Button size="sm" variant="ghost" onClick={() => setShowRaw(!showRaw)}><Code2 className="size-4" /> Model output</Button>}
            <Button size="sm" variant="secondary" onClick={() => setEditing(!editing)}><Pencil className="size-4" /> Override</Button>
          </div>
        )}
      </div>
      <SegmentFeedback seg={seg} attemptId={attemptId} />
      {showRaw && aiMarking?.raw && (
        <pre className="mt-4 max-h-80 overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">{JSON.stringify(aiMarking.raw, null, 2)}</pre>
      )}
      {editing && r && (
        <OverrideEditor responseId={r.id} initial={r.marking?.issues ?? []} rubric={rubric}
          onDone={(res) => { setEditing(false); onSaved(res); }} onCancel={() => setEditing(false)} />
      )}
    </div>
  );
}

function OverrideEditor({ responseId, initial, rubric, onDone, onCancel }:
  { responseId: string; initial: Issue[]; rubric: Rubric; onDone: (r: Results) => void; onCancel: () => void }) {
  const [issues, setIssues] = useState<Issue[]>(initial.map((i) => ({ ...i })));
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const pts = issues.reduce((a, i) => a + (rubric.severity_points[i.severity] ?? 0), 0);

  const update = (n: number, patch: Partial<Issue>) => setIssues(issues.map((x, i) => (i === n ? { ...x, ...patch } : x)));
  const save = async () => {
    setSaving(true);
    setErr("");
    try {
      const res = await api<Results>(`/admin/responses/${responseId}/override`, { method: "POST", json: { issues, note } });
      onDone(res);
    } catch (e) { setErr((e as Error).message); setSaving(false); }
  };

  return (
    <div className="mt-4 rounded-xl border-2 border-brand-200 bg-brand-50/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-semibold">Assessor override</div>
        <div className="text-sm tabular-nums text-slate-600">−{pts} pts before scaling</div>
      </div>
      <div className="space-y-2">
        {issues.map((iss, n) => {
          const cat = rubric.categories.find((c) => c.id === iss.category);
          return (
            <div key={n} className="grid gap-2 rounded-lg bg-white p-3 ring-1 ring-slate-200 md:grid-cols-[140px_140px_110px_1fr_auto]">
              <select value={iss.category} onChange={(e) => update(n, { category: e.target.value, check: rubric.categories.find((c) => c.id === e.target.value)!.checks[0].id })}
                className="h-9 rounded border border-slate-300 bg-white px-2 text-sm">
                {rubric.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select value={iss.check} onChange={(e) => update(n, { check: e.target.value })} className="h-9 rounded border border-slate-300 bg-white px-2 text-sm">
                {cat?.checks.map((c) => <option key={c.id} value={c.id}>{c.id.replace(/_/g, " ")}</option>)}
              </select>
              <select value={iss.severity} onChange={(e) => update(n, { severity: e.target.value as Issue["severity"] })} className="h-9 rounded border border-slate-300 bg-white px-2 text-sm">
                {Object.keys(rubric.severity_points).map((s) => <option key={s}>{s}</option>)}
              </select>
              <input value={iss.explanation} onChange={(e) => update(n, { explanation: e.target.value })} placeholder="Explanation for the student"
                className="h-9 rounded border border-slate-300 px-2 text-sm" />
              <button onClick={() => setIssues(issues.filter((_, i) => i !== n))} className="rounded p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600" aria-label="Remove issue">
                <Trash2 className="size-4" />
              </button>
            </div>
          );
        })}
        <button onClick={() => setIssues([...issues, { category: "accuracy", check: "omission", severity: "minor", quote: "", explanation: "" }])}
          className="inline-flex items-center gap-1 text-sm text-brand-600 hover:underline"><Plus className="size-4" /> Add issue</button>
      </div>
      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="Note to the student (required), e.g. why the score changed"
        className="mt-3 w-full rounded-lg border border-slate-300 p-2 text-sm" />
      {err && <div className="mt-2"><ErrorNote>{err}</ErrorNote></div>}
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button onClick={save} loading={saving} disabled={!note.trim()}>Save override</Button>
      </div>
    </div>
  );
}
