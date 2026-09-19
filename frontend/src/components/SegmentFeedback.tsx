"use client";

import { AlertTriangle, Bot, CheckCircle2, UserCheck } from "lucide-react";
import type { ReactNode } from "react";

import { type Issue, isHindi, LANG, type SegmentResult } from "@/lib/api";
import { Badge, cx, SeverityBadge } from "./ui";

const SEV_MARK: Record<string, string> = {
  critical: "bg-rose-100 text-rose-900 decoration-rose-400",
  major: "bg-amber-100 text-amber-900 decoration-amber-400",
  minor: "bg-slate-200/70 text-slate-900 decoration-slate-400",
};

const CATEGORY: Record<string, string> = {
  accuracy: "Accuracy", language_quality: "Language quality", register: "Register", delivery: "Delivery",
};

export function Highlighted({ text, issues }: { text: string; issues: Issue[] }) {
  const lower = text.toLowerCase();
  const ranges: { s: number; e: number; sev: string; n: number }[] = [];
  issues.forEach((iss, n) => {
    const q = (iss.quote || "").trim();
    if (!q || q === "...") return;
    const at = lower.indexOf(q.toLowerCase());
    if (at >= 0) ranges.push({ s: at, e: at + q.length, sev: iss.severity, n: n + 1 });
  });
  ranges.sort((a, b) => a.s - b.s);
  const out: ReactNode[] = [];
  let pos = 0;
  for (const r of ranges) {
    if (r.s < pos) continue;
    if (r.s > pos) out.push(text.slice(pos, r.s));
    out.push(
      <mark key={r.s} className={cx("rounded px-0.5 underline decoration-2 underline-offset-4", SEV_MARK[r.sev])}>
        {text.slice(r.s, r.e)}<sup className="ml-0.5 text-[10px] font-semibold no-underline">{r.n}</sup>
      </mark>,
    );
    pos = r.e;
  }
  out.push(text.slice(pos));
  return <>{out}</>;
}

function TextBlock({ label, text, children, tone = "plain" }: { label: string; text?: string; children?: ReactNode; tone?: "plain" | "muted" }) {
  const hi = text ? isHindi(text) : false;
  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</div>
      <div className={cx("text-[15px]", hi && "hindi", tone === "muted" ? "text-slate-500" : "text-ink")} lang={hi ? "hi" : "en"}>
        {children ?? text}
      </div>
    </div>
  );
}

export function IssueList({ issues }: { issues: Issue[] }) {
  if (issues.length === 0)
    return <div className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="size-4" /> No issues found in this segment.</div>;
  return (
    <ol className="space-y-2.5">
      {issues.map((iss, i) => (
        <li key={i} className="flex gap-3 text-sm">
          <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">{i + 1}</span>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <SeverityBadge severity={iss.severity} />
              <span className="font-medium text-slate-700">{CATEGORY[iss.category] ?? iss.category}</span>
              <span className="text-slate-400">· {iss.check.replace(/_/g, " ")}</span>
              {iss.possibly_transcription_error && <Badge tone="violet">possible mis-hearing</Badge>}
            </div>
            <p className="mt-0.5 text-slate-600">{iss.explanation}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function MarkingSource({ seg }: { seg: SegmentResult }) {
  const m = seg.response?.marking;
  if (!m) return null;
  if (m.source === "assessor")
    return <Badge tone="green"><UserCheck className="size-3" /> Reviewed by assessor</Badge>;
  return <Badge tone="brand"><Bot className="size-3" /> Marked by AI{m.marker === "heuristic" ? " (static rules)" : ""}</Badge>;
}

export default function SegmentFeedback({ seg, attemptId, showAudio = true }: { seg: SegmentResult; attemptId: string; showAudio?: boolean }) {
  const r = seg.response;
  const m = r?.marking;
  const target = seg.speaker === "en" ? "hi" : "en";
  return (
    <div className="space-y-5">
      <div className="grid gap-5 md:grid-cols-2">
        <TextBlock label={`Speaker said (${LANG[seg.speaker as "en" | "hi"]})`} text={seg.source_text} />
        <TextBlock label={`You said (${LANG[target]})`} text={r?.transcript}>
          {!r || !r.transcript ? <span className="italic text-slate-400">No interpretation recorded</span>
            : <Highlighted text={r.transcript} issues={m?.issues ?? []} />}
        </TextBlock>
      </div>
      {showAudio && r?.has_audio && (
        <audio controls preload="none" className="h-9 w-full max-w-md" src={`/api/attempts/${attemptId}/responses/${r.id}/audio`} />
      )}
      {r?.stt_provider === "mock" && (
        <p className="flex items-center gap-1.5 text-xs text-violet-700"><AlertTriangle className="size-3.5" />
          Demo mode: no speech-to-text key configured, so a sample transcript is shown instead of your words.</p>
      )}
      {r?.stt_provider === "browser" && (
        <p className="flex items-center gap-1.5 text-xs text-slate-500"><AlertTriangle className="size-3.5" />
          Transcribed by your browser&apos;s speech recognition, which is less accurate than server transcription. Listen to your recording to check.</p>
      )}
      {r?.needs_review && m?.source !== "assessor" && (
        <p className="flex items-center gap-1.5 text-xs text-amber-700"><AlertTriangle className="size-3.5" />
          Audio or transcript unclear. This segment has been sent to an assessor for review.</p>
      )}
      {r?.status === "error" && (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">Marking failed: {r.error}. An assessor will mark this segment.</p>
      )}
      {m && (
        <div className="rounded-lg bg-slate-50 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-semibold">Feedback</div>
            <div className="flex items-center gap-2">
              <MarkingSource seg={seg} />
              <span className="text-xs text-slate-500">−{m.points_deducted} pts before scaling</span>
            </div>
          </div>
          <IssueList issues={m.issues} />
          {m.source === "assessor" && m.note && (
            <div className="mt-4 rounded-md border-l-2 border-emerald-500 bg-white px-3 py-2 text-sm">
              <span className="font-medium">Assessor note:</span> {m.note}
            </div>
          )}
          {r?.ai_marking && (
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-slate-500">Original AI marking (−{r.ai_marking.points_deducted} pts)</summary>
              <div className="mt-2 opacity-70"><IssueList issues={r.ai_marking.issues} /></div>
            </details>
          )}
        </div>
      )}
      <TextBlock label="A model interpretation" text={seg.reference_text} tone="muted" />
    </div>
  );
}
