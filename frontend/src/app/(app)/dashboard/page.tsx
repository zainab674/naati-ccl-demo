"use client";

import { CalendarDays, ClipboardCheck, GraduationCap, MessagesSquare, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import AnnouncementCarousel from "@/components/AnnouncementCarousel";
import AttemptRow from "@/components/AttemptRow";
import { Card, cx, ErrorNote, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { courseAction, type Dashboard, type Performance, type TopicAverage } from "@/lib/student";

export default function DashboardPage() {
  const [d, setD] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { api<Dashboard>("/dashboard").then(setD).catch((e) => setError(e.message)); }, []);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!d) return <Spinner />;

  return (
    <>
      <PageHeader title="Welcome back!"
        subtitle={d.user.days_to_exam !== null && d.user.days_to_exam >= 0
          ? <span className="inline-flex items-center gap-1"><CalendarDays className="size-4" /> {d.user.days_to_exam} days to your test</span>
          : "Your CCL exam preparation progress and personalised recommendations."} />

      <AnnouncementCarousel items={d.announcements} />

      {!d.user.has_active_plan && (
        <Card className="mb-6 flex flex-wrap items-center justify-between gap-4 bg-brand-50 p-5 ring-brand-100">
          <div className="text-sm text-brand-900">You&apos;re on the free plan: the introduction course and free dialogues are open. Choose a plan for every dialogue and full mock tests.</div>
          <LinkButton href="/pricing">See plans</LinkButton>
        </Card>
      )}

      {d.unfinished.length > 0 && (
        <Card className="mb-6 overflow-hidden ring-amber-200">
          <div className="bg-amber-50 px-5 py-3 text-sm font-semibold text-amber-900">Continue where you left off</div>
          <div className="divide-y divide-slate-100">{d.unfinished.map((a) => <AttemptRow key={a.id} a={a} />)}</div>
        </Card>
      )}

      {d.scores_shown ? <PerformanceSummary d={d} /> : <PracticeFeedbackOnly />}
      <NextSteps d={d} />
      <RecentAttempts d={d} />
    </>
  );
}

function Average({ title, value, max, tone }: { title: string; value: number | null; max: number; tone: "green" | "orange" }) {
  const c = tone === "green" ? { bg: "bg-emerald-50", track: "bg-emerald-100", bar: "bg-emerald-500" } : { bg: "bg-orange-50", track: "bg-orange-100", bar: "bg-orange-400" };
  return (
    <div className={cx("rounded-xl p-4", c.bg)}>
      <strong className="text-sm">{title}</strong>
      <div className="mt-1 text-3xl font-bold tabular-nums">{value ?? "–"} <span className="text-base font-normal">/ {max}</span></div>
      <div className={cx("mt-2 h-2 overflow-hidden rounded-full", c.track)}><div className={cx("h-full", c.bar)} style={{ width: `${value === null ? 0 : (100 * value) / max}%` }} /></div>
    </div>
  );
}

function PerformanceSummary({ d }: { d: Dashboard }) {
  const p = d.performance;
  return (
    <Card className="p-6">
      {!d.scores_validated && (
        <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">Staff view: students of this language do not see these scores until scoring is validated.</p>
      )}
      <h2 className="text-xl font-semibold">Performance Summary</h2>
      <p className="text-sm text-slate-500">Your recent mock test results and dialogue practice performance. Estimated scores, not official NAATI results.</p>
      <div className="mt-5 grid gap-4 lg:grid-cols-[1.2fr_.85fr_1fr]">
        <div className="flex min-h-48 flex-col justify-between rounded-xl bg-brand-900 p-6 text-white">
          <div>Total Average Score</div>
          <div><strong className="text-5xl tabular-nums">{p.total_average ?? "–"}</strong> <span className="text-2xl text-brand-200">/ {d.mock_max}</span></div>
          <div>
            <div className="h-2 overflow-hidden rounded-full bg-white/20"><div className="h-full bg-brand-300" style={{ width: `${p.total_average === null ? 0 : (100 * p.total_average) / d.mock_max}%` }} /></div>
            <div className="mt-2 text-xs text-brand-100">{p.mocks_counted ? `Average of last ${p.mocks_counted} mock test${p.mocks_counted === 1 ? "" : "s"}` : "No mock tests yet"}</div>
          </div>
        </div>
        <div className="grid gap-3">
          <Average title="Easy Dialogues" value={p.easy_average} max={d.dialogue_max} tone="green" />
          <Average title="Difficult Dialogues" value={p.difficult_average} max={d.dialogue_max} tone="orange" />
        </div>
        <div className="rounded-xl bg-slate-50 p-5">
          <strong className="flex items-center gap-1.5"><Sparkles className="size-4 text-brand-600" /> {p.message.title}</strong>
          <p className="mt-3 text-sm leading-relaxed text-slate-600">{p.message.text}</p>
        </div>
      </div>

      <hr className="my-7 border-slate-200" />
      <h2 className="text-lg font-semibold">Your Performance per Category</h2>
      <p className="text-sm text-slate-500">Average of the last {d.average_over ?? "few"} completed practice dialogues in each category · Out of {d.dialogue_max}</p>
      <CategoryChart p={p} max={d.dialogue_max} />
      {p.focus.length > 0 && (
        <div className="mt-5 rounded-xl bg-slate-50 p-5">
          <strong className="flex items-center gap-1.5"><Sparkles className="size-4 text-brand-600" /> Focus on These Topics</strong>
          <p className="mt-2 text-sm text-slate-600">Prioritise {p.focus.map((f, i) => (
            <span key={f.topic}>{i > 0 && (i === p.focus.length - 1 ? " and " : ", ")}<strong>{f.topic} ({f.average}/{d.dialogue_max})</strong></span>
          ))} to strengthen your performance.</p>
        </div>
      )}
    </Card>
  );
}

function CategoryChart({ p, max }: { p: Performance; max: number }) {
  const m = p.markers;
  const lines = [{ label: `Conditional ${m.conditional}`, value: m.conditional, color: "#e3a13a" }, { label: `Pass ${m.pass}`, value: m.pass, color: "#db8744" },
    { label: `Safe ${m.safe}`, value: m.safe, color: "#239d6d" }];
  const low = (c: TopicAverage) => c.average !== null && c.average < m.conditional;
  return (
    <div className="mt-5" role="img" aria-label={`Average score per category out of ${max}`}>
      {p.categories.map((c) => (
        <div key={c.topic} className="my-3 grid grid-cols-[6.5rem_minmax(0,1fr)_1.75rem] items-center gap-2 sm:grid-cols-[11rem_minmax(0,1fr)_2.5rem] sm:gap-4">
          <div className={cx("text-right text-xs sm:text-sm", low(c) ? "font-bold text-rose-700" : "text-slate-600")}>{c.topic}</div>
          <div className="relative h-4.5 rounded-sm bg-slate-100" title={c.average === null ? `${c.topic}: not practised yet` : `${c.topic}: ${c.average} out of ${max}`}>
            {c.average !== null && <div className={cx("h-full rounded-sm", low(c) ? "bg-rose-500" : "bg-brand-500")} style={{ width: `${(100 * c.average) / max}%` }} />}
            {lines.map((l) => <span key={l.label} className="absolute -top-1 h-6.5 border-l-2 border-dashed" style={{ left: `${(100 * l.value) / max}%`, borderColor: l.color }} />)}
          </div>
          <span className={cx("text-sm font-bold tabular-nums", low(c) && "text-rose-700", c.average === null && "font-normal text-slate-400")}>{c.average ?? "–"}</span>
        </div>
      ))}
      <div className="mt-4 flex flex-wrap justify-end gap-5 text-xs text-slate-500">
        {lines.map((l) => <span key={l.label} className="flex items-center gap-1.5"><i className="inline-block h-3.5 border-l-2 border-dashed" style={{ borderColor: l.color }} />{l.label}</span>)}
      </div>
    </div>
  );
}

function PracticeFeedbackOnly() {
  return (
    <Card className="p-6">
      <h2 className="text-xl font-semibold">Performance Summary</h2>
      <p className="mt-2 max-w-3xl text-sm text-slate-600">You get feedback on every practice attempt: the errors found, why they matter and a suggested version.
        Estimated scores will appear here once scoring for your language has been checked against certified examiners.</p>
    </Card>
  );
}

function NextSteps({ d }: { d: Dashboard }) {
  const weakest = d.performance.focus[0]?.topic;
  const action = d.recommended_course ? courseAction(d.recommended_course) : null;
  const cards = [
    { icon: GraduationCap, color: "text-violet-600", eyebrow: "RECOMMENDED COURSE", title: d.recommended_course?.title ?? "Courses",
      text: d.recommended_course?.description || "Structured lessons and guided practice.", label: "Go to Course", href: action?.href ?? "/courses" },
    { icon: MessagesSquare, color: "text-emerald-600", eyebrow: "TARGETED PRACTICE", title: "Practise a Dialogue",
      text: weakest && d.scores_shown ? `Work on ${weakest}, your lowest category.` : "Work on topics that need improvement.", label: "Practise Dialogue",
      href: `/mock-tests?mode=dialogue${weakest && d.scores_shown ? `&topic=${encodeURIComponent(weakest)}` : ""}` },
    { icon: ClipboardCheck, color: "text-blue-600", eyebrow: "EXAM SIMULATION", title: "Take a Full Mock Test",
      text: "Assess your readiness with two dialogues.", label: "Start Mock Test", href: "/mock-tests?mode=full" },
  ];
  return (
    <Card className="mt-6 p-6">
      <h2 className="text-xl font-semibold">What Would You Like to Do Next?</h2>
      <p className="text-sm text-slate-500">Choose a recommended next step.</p>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <article key={c.eyebrow} className="flex min-h-44 flex-col gap-3 rounded-xl border border-slate-200 p-4">
              <div className="flex items-start gap-3">
                <Icon className={cx("size-6 shrink-0", c.color)} />
                <div className="min-w-0">
                  <div className={cx("text-xs font-bold", c.color)}>{c.eyebrow}</div>
                  <div className="mt-1 font-bold leading-snug">{c.title}</div>
                  <div className="mt-1 line-clamp-2 text-xs text-slate-500">{c.text}</div>
                </div>
              </div>
              <Link href={c.href} className="mt-auto rounded-full bg-ink py-2.5 text-center text-sm font-bold text-white hover:opacity-85">{c.label}</Link>
            </article>
          );
        })}
      </div>
    </Card>
  );
}

function RecentAttempts({ d }: { d: Dashboard }) {
  const [tab, setTab] = useState<"passed" | "other">("passed");
  // Without visible scores there is nothing to sort by, so all attempts are listed together.
  const rows = d.scores_shown ? d.recent.filter((a) => a.outcome === tab || (tab === "other" && !a.outcome)) : d.recent;
  const tabClass = (on: boolean) => cx("border-b-[3px] px-1 py-3 text-sm font-bold", on ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500");
  return (
    <Card className="mt-6 p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Recent Attempts</h2>
          <p className="text-sm text-slate-500">Review your completed dialogues and mock tests.</p>
        </div>
        <Link href="/attempts" className="shrink-0 text-sm text-brand-600 hover:underline">All attempts</Link>
      </div>
      {d.scores_shown && (
        <div role="tablist" aria-label="Attempt results" className="mt-3 flex gap-7 border-b border-slate-200">
          <button role="tab" aria-selected={tab === "passed"} className={tabClass(tab === "passed")} onClick={() => setTab("passed")}>Passed</button>
          <button role="tab" aria-selected={tab === "other"} className={tabClass(tab === "other")} onClick={() => setTab("other")}>Failed / Conditional</button>
        </div>
      )}
      {rows.length === 0 ? <p className="mt-4 text-sm text-slate-500">{d.recent.length ? "No attempts here yet." : "Your finished attempts will appear here."}</p>
        : <div className="-mx-6 mt-1 divide-y divide-slate-100">{rows.map((a) => <AttemptRow key={a.id} a={a} />)}</div>}
    </Card>
  );
}
