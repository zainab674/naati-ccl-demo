"use client";

import { Info, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import SegmentResultCard, { fmtDed } from "@/components/SegmentResultCard";
import { Badge, Card, ErrorNote, PageHeader, ScoreRing, Spinner } from "@/components/ui";
import { api, fmtDate, fmtDateTime } from "@/lib/api";
import type { Results } from "@/lib/results";

const SCORING = ["Pending", "Processing"];

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Results | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const x = await api<Results>(`/attempts/${id}/results`);
        if (!alive) return;
        setR(x);
        if (SCORING.includes(x.scoring_status)) timer = setTimeout(load, 4000);
      } catch (e) { if (alive) setError((e as Error).message); }
    };
    load();
    return () => { alive = false; clearTimeout(timer); };
  }, [id]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!r) return <Spinner />;
  const scoring = SCORING.includes(r.scoring_status);
  const done = r.total_score !== null && !scoring;
  const totalSegs = r.dialogues.reduce((n, d) => n + d.segments.length, 0);

  return (
    <>
      <PageHeader title={r.title} subtitle={<>{r.kind === "mock" ? "Mock test" : "Practice dialogue"}{r.submitted_at && ` · submitted ${fmtDateTime(r.submitted_at)}`}</>}
        actions={<Link href="/attempts" className="text-sm text-brand-600 hover:underline">All attempts</Link>} />

      {r.demo_scoring && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200">
          <Info className="size-4 shrink-0" /> Development mode: speech recognition and/or AI evaluation are simulated. Scores are not meaningful.
        </div>
      )}

      {scoring ? (
        <Card className="flex items-center gap-4 p-6">
          <Loader2 className="size-6 animate-spin text-brand-500" />
          <div><div className="font-semibold">Scoring your answers…</div>
            <div className="text-sm text-slate-500">{totalSegs - r.pending_segments} of {totalSegs} segments done. We will also email you when your results are ready.</div></div>
        </Card>
      ) : (
        <Card className="p-6">
          <div className="flex flex-wrap items-center gap-8">
            {done && <ScoreRing score={r.total_score!} max={r.maximum_score} passed={r.result === "Pass"} />}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-500">Estimated result</span>
                {r.result && <Badge tone={r.result === "Pass" ? "green" : "red"} className="text-sm">{r.result}</Badge>}
                {r.scoring_status === "Failed" && <Badge tone="amber">Some segments are waiting for a teacher</Badge>}
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {r.kind === "mock" ? `Pass: at least ${r.pass_rules.pass_total}/${r.pass_rules.total_max} overall and ${r.pass_rules.pass_min_per_dialogue} in each dialogue.`
                  : `Each dialogue is marked out of ${r.pass_rules.dialogue_max}; the minimum in the test is ${r.pass_rules.pass_min_per_dialogue}.`}
              </p>
              {r.reasons.length > 0 && <ul className="mt-2 list-disc pl-5 text-sm text-rose-700">{r.reasons.map((x) => <li key={x}>{x}</li>)}</ul>}
              <div className="mt-4 grid grid-cols-3 gap-3 sm:max-w-md">
                {([["Accuracy & completeness", r.deductions.accuracy], ["Language quality", r.deductions.language], ["Fluency", r.deductions.fluency]] as const).map(([label, v]) => (
                  <div key={label} className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-slate-500">{label}</div>
                    <div className="text-lg font-semibold tabular-nums text-rose-700">{fmtDed(v)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <p className="mt-4 text-xs text-slate-500">This is an estimated score to guide your practice, not an official NAATI result.</p>
        </Card>
      )}

      {r.dialogues.map((d) => (
        <section key={d.dialogue_attempt_id} className="mt-8">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Dialogue {d.position}{d.topic ? ` · ${d.topic}` : ""}</div>
              <h2 className="text-lg font-semibold">{d.title}</h2>
            </div>
            {d.score !== null && (
              <div className="text-right text-sm">
                <span className="text-xl font-semibold tabular-nums">{d.score}</span><span className="text-slate-500">/{d.maximum_score}</span>
                <span className="ml-2 text-slate-500">({fmtDed(d.deductions.accuracy)} accuracy, {fmtDed(d.deductions.language)} language, {fmtDed(d.deductions.fluency)} fluency{d.total_repeats ? `, ${d.total_repeats} repeat${d.total_repeats > 1 ? "s" : ""}` : ""})</span>
              </div>
            )}
          </div>
          <div className="space-y-2">
            {d.segments.map((s, i) => (
              <SegmentResultCard key={s.segment_attempt_id} seg={s} defaultOpen={i === 0 && !scoring}
                recordingUrl={`/api/attempts/${r.id}/segments/${s.segment_attempt_id}/recording`} />
            ))}
          </div>
        </section>
      ))}

      {r.history.length > 1 && (
        <Card className="mt-8 overflow-hidden">
          <div className="px-5 py-4 font-semibold">Your attempts at this {r.kind === "mock" ? "mock test" : "dialogue"}</div>
          <ul className="divide-y divide-slate-100 border-t border-slate-100">
            {r.history.map((h) => (
              <li key={h.id}>
                <Link href={`/results/${h.id}`} className="flex items-center justify-between px-5 py-3 text-sm hover:bg-slate-50">
                  <span>{h.submitted_at ? fmtDate(h.submitted_at) : ""}{h.id === r.id && <span className="ml-2 text-slate-400">(this attempt)</span>}</span>
                  <span className="flex items-center gap-2 tabular-nums">{h.total_score !== null ? `${h.total_score}/${h.maximum_score}` : "Scoring…"}{h.result && <Badge tone={h.result === "Pass" ? "green" : "red"}>{h.result}</Badge>}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
