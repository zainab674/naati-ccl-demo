import { CircleCheck, CircleX, Timer } from "lucide-react";

import { cx } from "../cx";

/**
 * Hero visual: a static example of one segment's feedback, built from the same vocabulary as SegmentResultCard.
 * The content is the worked example from docs/SCORING_BRIEF.md and is labelled "Example" on the page.
 * Deduction values mirror the default scoring config; this is illustration only, not live scoring.
 */
const ROWS = [
  { ok: true, label: "MU 1", text: "Your appointment", said: "Ang appointment ninyo" },
  { ok: true, label: "MU 2", text: "is on Tuesday", said: "ay sa Martes" },
  { ok: false, label: "MU 3 · Distortion", text: "at 10:30 in the morning", said: "alas-diyes ng umaga", fix: "alas-diyes y medya ng umaga", ded: "−1" },
];

// Deterministic bar heights for the recording strip (no randomness, so server and client render the same).
const BARS = [3, 5, 8, 6, 9, 7, 4, 8, 10, 6, 7, 9, 5, 8, 6, 9, 7, 5, 8, 4, 6, 3];

export function FeedbackPreview() {
  return (
    <figure aria-label="Example of segment feedback" className="relative">
      <div aria-hidden className="absolute -inset-6 -z-10 rounded-[2rem] bg-[radial-gradient(60%_60%_at_70%_30%,var(--color-brand-100),transparent)]" />
      <div className="overflow-hidden rounded-2xl bg-white shadow-[0_24px_60px_-28px_color-mix(in_oklab,var(--color-brand-950)_40%,transparent)] ring-1 ring-brand-900/10">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <span className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700">Segment 4</span>
            <span className="text-xs text-slate-500">English → Filipino</span>
          </div>
          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">Example</span>
        </div>

        <div className="space-y-4 px-5 py-5">
          <p className="rise text-[15px] leading-relaxed text-ink" style={{ "--d": "120ms" } as React.CSSProperties}>
            &ldquo;Your appointment is on Tuesday at 10:30 in the morning.&rdquo;
          </p>

          <ul className="divide-y divide-slate-100 rounded-xl ring-1 ring-slate-100">
            {ROWS.map((r, i) => (
              <li key={r.label} className="rise flex items-start gap-3 px-3.5 py-3" style={{ "--d": `${260 + i * 140}ms` } as React.CSSProperties}>
                {r.ok
                  ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                  : <CircleX className="mt-0.5 size-4 shrink-0 text-rose-600" />}
                <div className="min-w-0 flex-1 text-sm">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className={cx("text-xs font-semibold", r.ok ? "text-slate-400" : "text-rose-700")}>{r.label}</span>
                    <span className="font-medium text-ink">{r.text}</span>
                  </div>
                  <div className="mt-0.5 text-slate-500">You said: <bdi lang="fil" className={cx(!r.ok && "text-rose-700 line-through decoration-rose-300")}>{r.said}</bdi></div>
                  {r.fix && <div className="mt-0.5 text-emerald-800">Suggested: <bdi lang="fil">{r.fix}</bdi></div>}
                </div>
                <span className={cx("text-sm font-semibold tabular-nums", r.ded ? "text-rose-700" : "text-slate-300")}>{r.ded ?? "0"}</span>
              </li>
            ))}
          </ul>

          <div className="rise rounded-xl bg-slate-50 px-3.5 py-3" style={{ "--d": "720ms" } as React.CSSProperties}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2 font-medium text-ink"><Timer className="size-4 text-amber-600" />Started after 6.2 s</span>
              <span className="font-semibold tabular-nums text-rose-700">−0.5</span>
            </div>
            <div aria-hidden className="mt-3 flex h-7 items-end gap-[3px]">
              <div className="mr-1 h-full w-[26%] rounded-sm border border-dashed border-amber-300 bg-amber-50" />
              {BARS.map((h, i) => (
                <span key={i} className="max-w-2 flex-1 rounded-full bg-brand-400/80" style={{ height: `${h * 10}%` }} />
              ))}
            </div>
          </div>
        </div>

        <div className="rise flex items-center justify-between border-t border-slate-100 bg-brand-950 px-5 py-3.5 text-white" style={{ "--d": "860ms" } as React.CSSProperties}>
          <span className="text-sm text-brand-100/80">Segment deductions</span>
          <span className="font-display text-lg font-semibold tabular-nums">−1.5</span>
        </div>
      </div>
    </figure>
  );
}
