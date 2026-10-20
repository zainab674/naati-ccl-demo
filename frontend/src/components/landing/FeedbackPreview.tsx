"use client";

import { CircleCheck, CircleX, Timer } from "lucide-react";
import { animate, motion, useInView, useMotionValue, useTransform } from "motion/react";
import { useEffect, useRef } from "react";

import { cx } from "../cx";
import { EASE, useReduced } from "./motion";

/**
 * Example of one segment's feedback, built from the same vocabulary as SegmentResultCard.
 * The content is the worked example from docs/SCORING_BRIEF.md and is labelled "Example" on the page.
 * Deduction values mirror the default scoring config; this is illustration only, not live scoring.
 * When it scrolls into view the marking plays out in order: source, each Meaning Unit, timing, total.
 */
const ROWS = [
  { ok: true, label: "MU 1", text: "Your appointment", said: "Ang appointment ninyo" },
  { ok: true, label: "MU 2", text: "is on Tuesday", said: "ay sa Martes" },
  { ok: false, label: "MU 3 · Distortion", text: "at 10:30 in the morning", said: "alas-diyes ng umaga", fix: "alas-diyes y medya ng umaga", ded: "−1" },
];

// Deterministic bar heights for the recording strip (no randomness, so server and client render the same).
const BARS = [3, 5, 8, 6, 9, 7, 4, 8, 10, 6, 7, 9, 5, 8, 6, 9, 7, 5, 8, 4, 6, 3];
const TOTAL = 1.5;

const step = (i: number) => ({
  hidden: { opacity: 0, y: 14, filter: "blur(4px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { delay: 0.15 + i * 0.18, duration: 0.6, ease: EASE } },
});

export function FeedbackPreview() {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.4 });
  const reduce = useReduced();
  const total = useMotionValue(reduce ? TOTAL : 0);
  const totalText = useTransform(total, (v) => `−${v.toFixed(1)}`);

  useEffect(() => {
    if (!inView) return;
    if (reduce) { total.set(TOTAL); return; }
    const c = animate(total, TOTAL, { delay: 1.1, duration: 0.9, ease: EASE });
    return () => c.stop();
  }, [inView, reduce, total]);

  const state = reduce || inView ? "show" : "hidden";

  return (
    <figure ref={ref} aria-label="Example of segment feedback" className="relative">
      <div aria-hidden className="absolute -inset-10 -z-10 rounded-[3rem] bg-[radial-gradient(55%_55%_at_60%_35%,color-mix(in_oklab,var(--color-brand-400)_40%,transparent),transparent)] blur-xl" />
      <div className="overflow-hidden rounded-3xl bg-white/[0.06] text-white shadow-[0_40px_100px_-40px_rgb(0_0_0/0.8)] ring-1 ring-white/15 backdrop-blur-xl">
        <div className="flex items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="rounded-md bg-brand-300/15 px-2 py-0.5 text-xs font-semibold text-brand-200 ring-1 ring-brand-300/30">Segment 4</span>
            <span className="text-xs text-brand-100/60">Sample answer</span>
          </div>
          <span className="rounded-md bg-amber-300/15 px-2 py-0.5 text-[11px] font-semibold text-amber-200 ring-1 ring-amber-300/30">Example</span>
        </div>

        <motion.div className="space-y-4 px-5 py-5" initial={false} animate={state}>
          <motion.p variants={step(0)} className="text-[15px] leading-relaxed text-white/90">
            &ldquo;Your appointment is on Tuesday at 10:30 in the morning.&rdquo;
          </motion.p>

          <ul className="divide-y divide-white/10 overflow-hidden rounded-2xl ring-1 ring-white/10">
            {ROWS.map((r, i) => (
              <motion.li key={r.label} variants={step(i + 1)} className={cx("relative flex items-start gap-3 px-4 py-3", !r.ok && "bg-rose-500/10")}>
                {!r.ok && !reduce && (
                  <motion.span aria-hidden className="absolute inset-0 ring-2 ring-inset ring-rose-400/60"
                    initial={{ opacity: 0 }} animate={inView ? { opacity: [0, 1, 0] } : undefined}
                    transition={{ delay: 1.0, duration: 1.2, ease: "easeOut" }} />
                )}
                {r.ok
                  ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-300" />
                  : <CircleX className="mt-0.5 size-4 shrink-0 text-rose-300" />}
                <div className="min-w-0 flex-1 text-sm">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className={cx("text-xs font-semibold", r.ok ? "text-white/40" : "text-rose-300")}>{r.label}</span>
                    <span className="font-medium text-white">{r.text}</span>
                  </div>
                  <div className="mt-0.5 text-white/55">You said: <bdi lang="fil" className={cx(!r.ok && "text-rose-300 line-through decoration-rose-300/50")}>{r.said}</bdi></div>
                  {r.fix && <div className="mt-0.5 text-emerald-300">Suggested: <bdi lang="fil">{r.fix}</bdi></div>}
                </div>
                <span className={cx("text-sm font-semibold tabular-nums", r.ded ? "text-rose-300" : "text-white/25")}>{r.ded ?? "0"}</span>
              </motion.li>
            ))}
          </ul>

          <motion.div variants={step(4)} className="rounded-2xl bg-white/[0.04] px-4 py-3 ring-1 ring-white/10">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2 font-medium text-white"><Timer className="size-4 text-amber-300" />Started after 6.2 s</span>
              <span className="font-semibold tabular-nums text-rose-300">−0.5</span>
            </div>
            <div aria-hidden className="relative mt-3 flex h-7 items-end gap-[3px]">
              {!reduce && (
                <motion.div className="pointer-events-none absolute inset-y-[-4px] left-0 w-full"
                  initial={{ x: "26%", opacity: 0 }}
                  animate={inView ? { x: ["26%", "100%"], opacity: [0, 1, 1, 0] } : undefined}
                  transition={{ delay: 1.6, duration: 3.4, ease: "easeInOut", repeat: Infinity, repeatDelay: 0.8 }}>
                  <span className="block h-full w-0.5 rounded-full bg-white shadow-[0_0_10px_white]" />
                </motion.div>
              )}
              <div className="mr-1 h-full w-[26%] rounded-sm border border-dashed border-amber-300/50 bg-amber-300/10" />
              {BARS.map((h, i) => (
                <motion.span key={i} className="max-w-2 flex-1 origin-bottom rounded-full bg-gradient-to-t from-brand-400 to-brand-200"
                  style={{ height: `${h * 10}%` }}
                  initial={false}
                  animate={reduce || !inView ? undefined : { scaleY: [0.2, 1] }}
                  transition={{ delay: 0.9 + i * 0.025, duration: 0.5, ease: EASE }} />
              ))}
            </div>
          </motion.div>
        </motion.div>

        <div className="flex items-center justify-between border-t border-white/10 bg-gradient-to-r from-brand-600/40 to-brand-400/10 px-5 py-4">
          <span className="text-sm text-brand-100/80">Segment deductions</span>
          <motion.span className="font-display text-xl font-semibold tabular-nums text-white">{totalText}</motion.span>
        </div>
      </div>
    </figure>
  );
}
