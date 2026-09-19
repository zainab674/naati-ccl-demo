"use client";

import { ChevronDown, Repeat } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import SegmentFeedback, { MarkingSource } from "@/components/SegmentFeedback";
import { Badge, Card, cx, LinkButton, ScoreRing, SeverityBadge, Spinner } from "@/components/ui";
import { api, type DialogueResult, fmtDateTime, type Results } from "@/lib/api";

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Results | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await api<Results>(`/attempts/${id}/results`);
        if (!alive) return;
        setR(data);
        if (data.status === "marking") setTimeout(load, 1500);
      } catch (e) { setErr((e as Error).message); }
    };
    load();
    return () => { alive = false; };
  }, [id]);

  if (err) return <Card className="p-8 text-center text-sm text-slate-500">{err}</Card>;
  if (!r) return <Spinner />;

  const isMock = r.mode === "mock";
  return (
    <div className="space-y-6">
      <Card className="p-6 sm:p-8">
        <div className="flex flex-wrap items-center gap-8">
          <ScoreRing score={r.total} max={r.total_max} passed={r.passed} />
          <div className="min-w-60 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={isMock ? "violet" : "brand"}>{isMock ? "Mock test" : "Practice"}</Badge>
              {r.status === "marking" ? <Badge tone="amber">Marking {r.pending_segments} segments…</Badge> :
                <Badge tone={r.passed ? "green" : "red"}>{isMock ? (r.passed ? "PASS" : "BELOW PASS") : (r.passed ? "Meets dialogue minimum" : "Below dialogue minimum")}</Badge>}
              {r.reviewed_by_assessor ? <Badge tone="green">Reviewed by assessor</Badge> : <Badge>Marked by AI</Badge>}
            </div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight">{r.dialogues.map((d) => d.title).join(" + ")}</h1>
            <p className="mt-1 text-sm text-slate-500">
              {r.submitted_at ? `Submitted ${fmtDateTime(r.submitted_at)}` : ""} ·{" "}
              {isMock ? `Pass needs ${r.pass_rules.pass_total}/90 and at least ${r.pass_rules.pass_min_per_dialogue}/45 in each dialogue`
                : `A pass needs at least ${r.pass_rules.pass_min_per_dialogue}/45 per dialogue`}
            </p>
            {isMock && !r.passed && r.status === "marked" && (
              <p className="mt-3 text-sm text-rose-700">
                {r.total < r.pass_rules.pass_total ? `${r.pass_rules.pass_total - r.total} points short of the overall pass mark. ` : ""}
                {r.dialogues.filter((d) => !d.meets_minimum).map((d) => `${d.title} is below ${r.pass_rules.pass_min_per_dialogue}.`).join(" ")}
              </p>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {r.dialogues.map((d, i) => (
              <div key={d.activity_id} className="rounded-lg bg-slate-50 px-4 py-3">
                <div className="text-xs text-slate-500">Dialogue {i + 1}</div>
                <div className="text-xl font-semibold tabular-nums">{d.score}<span className="text-sm font-normal text-slate-400">/{d.max}</span></div>
                <div className={cx("text-xs", d.meets_minimum ? "text-emerald-600" : "text-rose-600")}>{d.meets_minimum ? "≥ 29" : "< 29"}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {r.dialogues.map((d, i) => <DialogueSection key={d.activity_id} d={d} n={i + 1} attemptId={r.attempt_id} />)}

      <div className="flex justify-center gap-3 pb-8">
        <LinkButton href="/library" variant="secondary">Practise another dialogue</LinkButton>
        <LinkButton href="/dashboard">Back to dashboard</LinkButton>
      </div>
    </div>
  );
}

function DialogueSection({ d, n, attemptId }: { d: DialogueResult; n: number; attemptId: string }) {
  const [open, setOpen] = useState<number | null>(d.segments.find((s) => (s.response?.marking?.issues.length ?? 0) > 0)?.index ?? null);
  const totalCat = d.by_category.reduce((a, c) => a + c.points, 0);
  return (
    <Card>
      <div className="border-b border-slate-100 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Dialogue {n} · {d.domain}</div>
            <h2 className="mt-1 text-lg font-semibold">{d.title}</h2>
          </div>
          <div className="text-right">
            <div className="text-2xl font-semibold tabular-nums">{d.score}<span className="text-sm font-normal text-slate-400">/45</span></div>
            <div className="flex items-center justify-end gap-1 text-xs text-slate-500">
              <Repeat className="size-3" /> {d.repeats_used} repeat{d.repeats_used === 1 ? "" : "s"}
              {d.repeat_deduction > 0 && <span className="text-rose-600">(−{d.repeat_deduction})</span>}
            </div>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          {d.by_category.map((c) => (
            <div key={c.id}>
              <div className="flex justify-between text-xs"><span className="text-slate-600">{c.name}</span><span className="tabular-nums text-slate-500">−{c.points}</span></div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-rose-400" style={{ width: totalCat ? `${(c.points / totalCat) * 100}%` : "0%" }} />
              </div>
            </div>
          ))}
        </div>
        {d.scale !== 1 && (
          <p className="mt-4 text-xs text-slate-400">This demo dialogue has {d.segments.length} segments, where a real CCL dialogue has about 35. Deductions are scaled ×{d.scale} so the score is on the exam&apos;s 45-point scale.</p>
        )}
      </div>
      <ul className="divide-y divide-slate-100">
        {d.segments.map((s) => {
          const issues = s.response?.marking?.issues ?? [];
          const worst = issues.find((x) => x.severity === "critical") ?? issues.find((x) => x.severity === "major") ?? issues[0];
          const isOpen = open === s.index;
          return (
            <li key={s.index}>
              <button onClick={() => setOpen(isOpen ? null : s.index)} className="flex w-full items-center gap-3 px-6 py-3.5 text-left hover:bg-slate-50">
                <span className="w-8 text-sm tabular-nums text-slate-400">{s.number}</span>
                <span className="w-16 text-xs text-slate-500">{s.speaker === "en" ? "EN → HI" : "HI → EN"}</span>
                <span className="flex-1 truncate text-sm">
                  {!s.response ? <span className="text-slate-400">Not answered</span> :
                    s.response.status === "uploaded" ? <span className="text-slate-400">Marking…</span> :
                    issues.length === 0 ? <span className="text-emerald-700">No issues</span> :
                    <span className="text-slate-600">{issues.length} issue{issues.length > 1 ? "s" : ""}: {worst?.explanation}</span>}
                </span>
                {worst && <SeverityBadge severity={worst.severity} />}
                {s.plays > 1 && <Badge><Repeat className="size-3" /></Badge>}
                {s.response?.marking?.source === "assessor" && <MarkingSource seg={s} />}
                <ChevronDown className={cx("size-4 text-slate-400 transition-transform", isOpen && "rotate-180")} />
              </button>
              {isOpen && <div className="bg-white px-6 pb-6 pt-2"><SegmentFeedback seg={s} attemptId={attemptId} /></div>}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
