"use client";

import { ChevronDown, Plus, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Card, cx, ErrorNote, Field, inputClass, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { api } from "@/lib/api";
import { statusTone } from "@/lib/admin";

type MU = { id?: string; meaning_unit_number: number; meaning: string; reference_interpretation: string; weight: number; active: boolean };
type Seg = {
  id: string; segment_number: number; direction: string; source_language: string; target_language: string;
  speaker_label: string; speaker_role: string; transcript: string; active: boolean; media_status: string; media_error: string;
  duration_seconds: number | null; source_audio_url: string; has_waveform: boolean; meaning_units: MU[];
};
type Detail = {
  id: string; key: string; title: string; topic_id: string | null; difficulty: string; status: string; is_free: boolean;
  version: number; description: string; instructions: string; maximum_score: number; passing_score: number;
  sort_order: number; publish_problems: string[]; segments: Seg[]; language_pair: string;
};

export default function DialogueEditor() {
  const { id } = useParams<{ id: string }>();
  const [d, setD] = useState<Detail | null>(null);
  const [topics, setTopics] = useState<{ id: string; name: string }[]>([]);
  const [form, setForm] = useState<Partial<Detail>>({});
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState("");

  const apply = useCallback((x: Detail) => {
    setD(x);
    setForm({ title: x.title, description: x.description, instructions: x.instructions, topic_id: x.topic_id,
      difficulty: x.difficulty, is_free: x.is_free, maximum_score: x.maximum_score, passing_score: x.passing_score, sort_order: x.sort_order });
  }, []);
  useEffect(() => {
    api<Detail>(`/admin/dialogues/${id}`).then(apply).catch((e) => setMsg({ err: e.message }));
    api<{ id: string; name: string }[]>("/admin/topics").then(setTopics).catch(() => {});
  }, [id, apply]);

  const save = async (patch: Partial<Detail>, label: string) => {
    setBusy(label);
    setMsg({});
    try {
      const x = await api<Detail>(`/admin/dialogues/${id}`, { method: "PATCH", json: patch });
      setD(x);
      setMsg({ ok: "Saved." });
    } catch (e) { setMsg({ err: (e as Error).message }); }
    setBusy("");
  };

  if (!d) return msg.err ? <ErrorNote>{msg.err}</ErrorNote> : <Spinner />;
  return (
    <>
      <PageHeader title={d.title}
        subtitle={<><span className="font-mono">{d.key}</span> · v{d.version} · {d.language_pair} · <Link href="/admin/dialogues" className="text-brand-600 hover:underline">All dialogues</Link></>}
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={statusTone(d.status)}>{d.status}</Badge>
            {d.status !== "Published" && <Button size="sm" onClick={() => save({ status: "Published" }, "status")} loading={busy === "status"} disabled={d.publish_problems.length > 0}>Publish</Button>}
            {d.status === "Published" && <Button size="sm" variant="secondary" onClick={() => save({ status: "Archived" }, "status")} loading={busy === "status"}>Hide</Button>}
            {d.status === "Archived" && <Button size="sm" variant="ghost" onClick={() => save({ status: "Draft" }, "status")}>Back to draft</Button>}
          </div>
        } />
      {msg.ok && <div className="mb-4"><SuccessNote>{msg.ok}</SuccessNote></div>}
      {msg.err && <div className="mb-4"><ErrorNote>{msg.err}</ErrorNote></div>}
      {d.publish_problems.length > 0 && (
        <div className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200">
          Not ready to publish: {d.publish_problems.join(" ")}
        </div>
      )}

      <Card className="mb-6 p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Title" value={form.title ?? ""} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <label className="block"><span className="text-sm font-medium text-slate-700">Topic</span>
            <select className={inputClass} value={form.topic_id ?? ""} onChange={(e) => setForm({ ...form, topic_id: e.target.value })}>
              {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select></label>
          <label className="block"><span className="text-sm font-medium text-slate-700">Difficulty</span>
            <select className={inputClass} value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })}>
              <option>Easy</option><option>Intermediate</option><option>Difficult</option>
            </select></label>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Max score" type="number" value={form.maximum_score ?? 45} onChange={(e) => setForm({ ...form, maximum_score: Number(e.target.value) })} />
            <Field label="Pass mark" type="number" value={form.passing_score ?? 29} onChange={(e) => setForm({ ...form, passing_score: Number(e.target.value) })} />
            <Field label="Sort" type="number" value={form.sort_order ?? 0} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
          </div>
          <label className="block sm:col-span-2"><span className="text-sm font-medium text-slate-700">Description</span>
            <textarea className={cx(inputClass, "h-20 py-2")} value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <label className="block sm:col-span-2"><span className="text-sm font-medium text-slate-700">Instructions (shown on each segment page)</span>
            <textarea className={cx(inputClass, "h-20 py-2")} value={form.instructions ?? ""} onChange={(e) => setForm({ ...form, instructions: e.target.value })} /></label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!form.is_free} onChange={(e) => setForm({ ...form, is_free: e.target.checked })} className="accent-brand-600" /> Free (open to students without a plan)</label>
          <div className="text-right"><Button onClick={() => save(form, "details")} loading={busy === "details"}>Save details</Button></div>
        </div>
      </Card>

      <h2 className="mb-3 text-lg font-semibold">Segments</h2>
      <div className="space-y-3">
        {d.segments.map((s) => <SegmentEditor key={s.id} seg={s} onSaved={setD} onError={(e) => setMsg({ err: e })} />)}
      </div>
    </>
  );
}

function SegmentEditor({ seg, onSaved, onError }: { seg: Seg; onSaved: (d: Detail) => void; onError: (e: string) => void }) {
  const [open, setOpen] = useState(false);
  const [transcript, setTranscript] = useState(seg.transcript);
  const [mus, setMus] = useState<MU[]>(seg.meaning_units.filter((m) => m.active));
  const [busy, setBusy] = useState("");
  // Reset local edits when the saved segment changes (React's "adjust state on prop change" pattern).
  const [prevSeg, setPrevSeg] = useState(seg);
  if (seg !== prevSeg) {
    setPrevSeg(seg);
    setTranscript(seg.transcript);
    setMus(seg.meaning_units.filter((m) => m.active));
  }

  const run = async (label: string, fn: () => Promise<Detail | unknown>) => {
    setBusy(label);
    try { const r = await fn(); if (r && typeof r === "object" && "segments" in r) onSaved(r as Detail); }
    catch (e) { onError((e as Error).message); }
    setBusy("");
  };
  const setMu = (i: number, patch: Partial<MU>) => setMus(mus.map((m, j) => (j === i ? { ...m, ...patch } : m)));
  const tone = seg.media_status === "ready" ? "green" : seg.media_status === "failed" ? "red" : "amber";

  return (
    <Card className={cx("overflow-hidden", !seg.active && "opacity-60")}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-5 py-3 text-left">
        <span className="w-8 font-semibold tabular-nums text-slate-400">{seg.segment_number}</span>
        <Badge>{seg.direction}</Badge>
        <span dir="auto" className="flex-1 truncate text-sm">{seg.transcript}</span>
        <Badge tone={tone}>{seg.media_status}</Badge>
        <span className="text-xs text-slate-500">{mus.length} MU</span>
        <ChevronDown className={cx("size-4 text-slate-400 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-5 border-t border-slate-100 px-5 py-5">
          {seg.has_waveform && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`/api/admin/segments/${seg.id}/waveform`} alt="Waveform" className="h-16 w-full rounded bg-slate-50 object-fill" />
          )}
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span>{seg.source_language} → {seg.target_language}</span>
            {seg.speaker_role && <span>· {seg.speaker_label} ({seg.speaker_role})</span>}
            {seg.duration_seconds && <span>· {seg.duration_seconds.toFixed(1)} s</span>}
            {seg.media_error && <span className="text-rose-700">· {seg.media_error}</span>}
            <button onClick={() => run("media", () => api(`/admin/segments/${seg.id}/reprocess-media`, { method: "POST" }))}
              className="inline-flex items-center gap-1 text-brand-600 hover:underline"><RefreshCw className="size-3" /> Re-process audio</button>
          </div>
          <label className="block"><span className="text-sm font-medium text-slate-700">Source transcript</span>
            <textarea dir="auto" className={cx(inputClass, "h-20 py-2")} value={transcript} onChange={(e) => setTranscript(e.target.value)} /></label>
          <div className="flex justify-between">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={seg.active} className="accent-brand-600"
              onChange={(e) => run("active", () => api(`/admin/segments/${seg.id}`, { method: "PATCH", json: { active: e.target.checked } }))} /> Active</label>
            <Button size="sm" variant="secondary" loading={busy === "transcript"} disabled={transcript === seg.transcript}
              onClick={() => run("transcript", () => api(`/admin/segments/${seg.id}`, { method: "PATCH", json: { transcript } }))}>Save transcript</Button>
          </div>

          <div>
            <div className="mb-2 text-sm font-medium text-slate-700">Meaning Units</div>
            <div className="space-y-2">
              {mus.map((m, i) => (
                <div key={m.id ?? `new-${i}`} className="grid grid-cols-[3rem_1fr_1fr_4rem_2rem] items-start gap-2">
                  <input type="number" min={1} value={m.meaning_unit_number} onChange={(e) => setMu(i, { meaning_unit_number: Number(e.target.value) })} className={cx(inputClass, "mt-0")} aria-label="Number" />
                  <textarea dir="auto" value={m.meaning} onChange={(e) => setMu(i, { meaning: e.target.value })} placeholder="Meaning that must be conveyed" className={cx(inputClass, "mt-0 h-16 py-2")} />
                  <textarea dir="auto" value={m.reference_interpretation} onChange={(e) => setMu(i, { reference_interpretation: e.target.value })} placeholder="Reference interpretation (optional)" className={cx(inputClass, "mt-0 h-16 py-2")} />
                  <input type="number" min={0.1} step={0.5} value={m.weight} onChange={(e) => setMu(i, { weight: Number(e.target.value) })} className={cx(inputClass, "mt-0")} aria-label="Weight" title="Weight" />
                  <button onClick={() => setMus(mus.filter((_, j) => j !== i))} className="mt-2 text-slate-400 hover:text-rose-600" aria-label="Remove"><Trash2 className="size-4" /></button>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap justify-between gap-2">
              <Button size="sm" variant="ghost" loading={busy === "suggest"} onClick={() => run("suggest", async () => {
                const r = await api<{ meaning_units: MU[]; model: string }>(`/admin/segments/${seg.id}/suggest-meaning-units`, { method: "POST" });
                if (mus.length && !confirm("Replace the meaning units below with the AI suggestion? Nothing is saved until you press Save.")) return;
                setMus(r.meaning_units.map((m) => ({ ...m, weight: 1, active: true })));
              })}>Suggest with AI</Button>
              <Button size="sm" variant="ghost" onClick={() => setMus([...mus, { meaning_unit_number: Math.max(0, ...mus.map((m) => m.meaning_unit_number)) + 1, meaning: "", reference_interpretation: "", weight: 1, active: true }])}>
                <Plus className="size-4" /> Add meaning unit
              </Button>
              <Button size="sm" loading={busy === "mus"}
                onClick={() => run("mus", () => api(`/admin/segments/${seg.id}/meaning-units`, { method: "PUT", json: mus }))}>Save meaning units</Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
