"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import SegmentResultCard, { fmtDed } from "@/components/SegmentResultCard";
import { Badge, Button, Card, cx, ErrorNote, inputClass, Modal, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { api } from "@/lib/api";
import type { Results, SegmentResult } from "@/lib/results";

type AdminAttempt = Results & {
  student: { id: string; name: string; email: string; subscription_status: string; flagged: boolean };
  integrity_events: { type: string; detail?: string; at: string }[];
};
type Run = { id: string; kind: string; provider: string; model: string; prompt_version: string; status: string; error_message: string;
  request_data: Record<string, unknown>; raw_response: unknown; processed_result: unknown; created_at: string };
type Target = { kind: string; id: string; deduction: number };

export default function AdminAttempt() {
  const { id } = useParams<{ id: string }>();
  const [a, setA] = useState<AdminAttempt | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [target, setTarget] = useState<{ seg: string; t: Target } | null>(null);
  const [runsFor, setRunsFor] = useState<string | null>(null);

  const load = useCallback(() => api<AdminAttempt>(`/admin/attempts/${id}`).then(setA), [id]);
  useEffect(() => { api<AdminAttempt>(`/admin/attempts/${id}`).then(setA).catch((e) => setError(e.message)); }, [id]);

  const action = async (path: string, body?: object, ok = "Saved.") => {
    setError("");
    try {
      await api(path, { method: "POST", json: body ?? {} });
      await load();
      setMsg(ok);
    } catch (e) { setError((e as Error).message); }
  };

  if (!a) return error ? <ErrorNote>{error}</ErrorNote> : <Spinner />;
  return (
    <>
      <PageHeader title={a.title ?? "Attempt"}
        subtitle={<><Link href={`/admin/students/${a.student.id}`} className="text-brand-600 hover:underline">{a.student.name}</Link> · {a.student.email} · <Badge>{a.student.subscription_status}</Badge></>}
        actions={<Link href="/admin/review" className="text-sm text-brand-600 hover:underline">Review queue</Link>} />
      {msg && <div className="mb-4"><SuccessNote>{msg}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}

      <Card className="mb-6 flex flex-wrap items-center gap-6 p-5 text-sm">
        <div><div className="text-slate-500">Total</div><div className="text-2xl font-semibold tabular-nums">{a.total_score ?? "–"}<span className="text-base text-slate-400">/{a.maximum_score}</span></div></div>
        {a.result && <Badge tone={a.result === "Pass" ? "green" : "red"}>{a.result}</Badge>}
        <Badge>{a.scoring_status}</Badge>
        {a.deductions && <span className="text-slate-600">{fmtDed(a.deductions.accuracy)} accuracy · {fmtDed(a.deductions.language)} language · {fmtDed(a.deductions.fluency)} fluency</span>}
        {a.demo_scoring && <Badge tone="amber">Mock providers</Badge>}
        {a.integrity_events.length > 0 && <span className="text-slate-500">Integrity: {a.integrity_events.map((e) => e.type).join(", ")}</span>}
      </Card>

      {a.dialogues.map((d) => (
        <section key={d.dialogue_attempt_id} className="mb-8">
          <h2 className="mb-3 text-lg font-semibold">Dialogue {d.position}: {d.title} <span className="text-sm font-normal text-slate-500">· {d.score ?? "–"}/{d.maximum_score} · v{d.dialogue_version} · {d.total_repeats} repeats</span></h2>
          <div className="space-y-3">
            {d.segments.map((s) => (
              <div key={s.segment_attempt_id} id={`seg-${s.segment_attempt_id}`}>
                <SegmentResultCard seg={s} defaultOpen={s.needs_review && !s.reviewed}
                  recordingUrl={`/api/attempts/${a.id}/segments/${s.segment_attempt_id}/recording`}
                  actions={(kind, item) => (
                    <button onClick={() => setTarget({ seg: s.segment_attempt_id, t: { kind, id: item.id, deduction: item.deduction } })}
                      className="text-xs font-medium text-brand-600 hover:underline">Override</button>
                  )} />
                <AdminSegmentTools seg={s} onAction={action} onRuns={() => setRunsFor(s.segment_attempt_id)} />
              </div>
            ))}
          </div>
        </section>
      ))}

      <OverrideModal target={target} onClose={() => setTarget(null)}
        onSave={async (revised, notes) => {
          if (!target) return;
          await action(`/admin/segment-attempts/${target.seg}/override`, { target_type: target.t.kind, target_id: target.t.id, revised_deduction: revised, notes }, "Deduction overridden; totals recalculated.");
          setTarget(null);
        }} />
      <RunsModal segmentAttemptId={runsFor} onClose={() => setRunsFor(null)} />
    </>
  );
}

function AdminSegmentTools({ seg, onAction, onRuns }: { seg: SegmentResult; onAction: (path: string, body?: object, ok?: string) => Promise<void>; onRuns: () => void }) {
  const [adding, setAdding] = useState(false);
  const [item, setItem] = useState({ criterion: "language", type: "Grammar", student_text: "", suggested_version: "", explanation: "" });
  const types: Record<string, string[]> = {
    language: ["Grammar", "UnidiomaticUsage", "Register", "SentenceStructure", "Pronunciation"],
    fluency: ["Hesitation", "SelfCorrection", "Pause", "StartDelay"], insertion: [""],
  };
  return (
    <div className="mt-1 flex flex-wrap items-center gap-3 px-2 text-xs text-slate-500">
      {seg.scoring_error && <span className="text-amber-700">{seg.scoring_error}</span>}
      {seg.scoring_confidence != null && <span>AI confidence {seg.scoring_confidence}</span>}
      {seg.stt_provider && <span>STT: {seg.stt_provider}</span>}
      <button onClick={onRuns} className="text-brand-600 hover:underline">AI output</button>
      <button onClick={() => setAdding(!adding)} className="text-brand-600 hover:underline">Add an error</button>
      {!seg.reviewed && <button onClick={() => onAction(`/admin/segment-attempts/${seg.segment_attempt_id}/reviewed`, { notes: "Reviewed" }, "Marked as reviewed.")} className="text-brand-600 hover:underline">Mark reviewed</button>}
      {seg.answered && <button onClick={() => { if (confirm("Re-run STT and AI evaluation for this segment? Current AI results are replaced.")) onAction(`/admin/segment-attempts/${seg.segment_attempt_id}/rescore`, {}, "Re-scoring queued."); }} className="text-brand-600 hover:underline">Re-score</button>}
      {seg.reviews && seg.reviews.length > 0 && <span>{seg.reviews.length} review note{seg.reviews.length > 1 ? "s" : ""}: {seg.reviews.map((r) => r.notes).join(" · ")}</span>}
      {adding && (
        <div className="mt-2 grid w-full gap-2 rounded-lg bg-white p-3 ring-1 ring-slate-200 sm:grid-cols-5">
          <select className={cx(inputClass, "mt-0")} value={item.criterion} onChange={(e) => setItem({ ...item, criterion: e.target.value, type: types[e.target.value][0] })}>
            <option value="language">Language quality</option><option value="fluency">Fluency</option><option value="insertion">Insertion</option>
          </select>
          {item.criterion !== "insertion" && <select className={cx(inputClass, "mt-0")} value={item.type} onChange={(e) => setItem({ ...item, type: e.target.value })}>
            {types[item.criterion].map((t) => <option key={t}>{t}</option>)}</select>}
          <input dir="auto" className={cx(inputClass, "mt-0")} placeholder="Student text" value={item.student_text} onChange={(e) => setItem({ ...item, student_text: e.target.value })} />
          <input className={cx(inputClass, "mt-0")} placeholder="Explanation (shown to student)" value={item.explanation} onChange={(e) => setItem({ ...item, explanation: e.target.value })} />
          <Button size="sm" onClick={async () => { await onAction(`/admin/segment-attempts/${seg.segment_attempt_id}/items`, item, "Error added; totals recalculated."); setAdding(false); }}>Add</Button>
        </div>
      )}
    </div>
  );
}

function OverrideModal({ target, onClose, onSave }: { target: { t: Target } | null; onClose: () => void; onSave: (revised: number, notes: string) => Promise<void> }) {
  const [value, setValue] = useState(0);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [prev, setPrev] = useState(target);
  if (target !== prev) { setPrev(target); setValue(0); setNotes(""); }
  return (
    <Modal open={!!target} onClose={onClose} title="Override deduction">
      {target && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">Current deduction: <b>{fmtDed(target.t.deduction)}</b>. Enter the deduction this item should carry (0 removes it).</p>
          <input type="number" step={0.5} min={0} className={inputClass} value={value} onChange={(e) => setValue(Number(e.target.value))} />
          <textarea className={cx(inputClass, "h-24 py-2")} placeholder="Note (required): why the deduction changes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button loading={busy} disabled={notes.trim().length < 3} onClick={async () => { setBusy(true); await onSave(value, notes); setBusy(false); }}>Save override</Button></div>
        </div>
      )}
    </Modal>
  );
}

function RunsModal({ segmentAttemptId, onClose }: { segmentAttemptId: string | null; onClose: () => void }) {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [prev, setPrev] = useState(segmentAttemptId);
  if (segmentAttemptId !== prev) { setPrev(segmentAttemptId); setRuns(null); }
  useEffect(() => { if (segmentAttemptId) api<Run[]>(`/admin/segment-attempts/${segmentAttemptId}/runs`).then(setRuns).catch(() => setRuns([])); }, [segmentAttemptId]);
  return (
    <Modal open={!!segmentAttemptId} onClose={onClose} title="AI scoring runs" wide>
      {!runs ? <Spinner /> : runs.length === 0 ? <p className="text-sm text-slate-500">No runs recorded.</p> : (
        <div className="space-y-4">
          {runs.map((r) => (
            <details key={r.id} className="rounded-lg ring-1 ring-slate-200" open={r.kind === "evaluation"}>
              <summary className="cursor-pointer px-4 py-2 text-sm"><b>{r.kind}</b> · {r.provider} / {r.model} {r.prompt_version && `· ${r.prompt_version}`} · <Badge tone={r.status === "Success" ? "green" : "red"}>{r.status}</Badge> {r.error_message}</summary>
              <div className="space-y-2 px-4 pb-4 text-xs">
                <div className="font-semibold">Processed result</div>
                <pre className="max-h-72 overflow-auto rounded bg-slate-50 p-3">{JSON.stringify(r.processed_result, null, 2)}</pre>
                <details><summary className="cursor-pointer font-semibold">Request</summary><pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3">{JSON.stringify(r.request_data, null, 2)}</pre></details>
                <details><summary className="cursor-pointer font-semibold">Raw response</summary><pre className="max-h-72 overflow-auto rounded bg-slate-50 p-3">{JSON.stringify(r.raw_response, null, 2)}</pre></details>
              </div>
            </details>
          ))}
        </div>
      )}
    </Modal>
  );
}
