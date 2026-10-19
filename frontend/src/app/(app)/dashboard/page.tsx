"use client";

import { ArrowRight, CalendarDays, ClipboardCheck, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AttemptRow from "@/components/AttemptRow";
import { Button, Card, ErrorNote, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { type Dashboard, minutes } from "@/lib/student";

export default function DashboardPage() {
  const router = useRouter();
  const [d, setD] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);

  useEffect(() => { api<Dashboard>("/dashboard").then(setD).catch((e) => setError(e.message)); }, []);

  const quickStart = async (id: string) => {
    setStarting(true);
    try {
      const r = await api<{ id: string }>("/attempts", { method: "POST", json: { dialogue_id: id } });
      router.push(`/attempt/${r.id}`);
    } catch (e) { setError((e as Error).message); setStarting(false); }
  };

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!d) return <Spinner />;
  const stats = [
    { label: "Average mock test score", value: d.average_mock_score !== null ? `${d.average_mock_score}` : "–", sub: `out of ${d.mock_max}` },
    { label: "Average dialogue score", value: d.average_dialogue_score !== null ? `${d.average_dialogue_score}` : "–", sub: `out of ${d.dialogue_max}` },
    { label: "Dialogues available", value: `${d.dialogues_available}`, sub: `of ${d.dialogues_total} in the library` },
    { label: "Mock tests available", value: `${d.mock_tests_available}`, sub: "two dialogues each" },
  ];

  return (
    <>
      <PageHeader title={`Welcome, ${d.user.first_name}`}
        subtitle={d.user.days_to_exam !== null && d.user.days_to_exam >= 0
          ? <span className="inline-flex items-center gap-1"><CalendarDays className="size-4" /> {d.user.days_to_exam} days to your test</span>
          : "Your CCL practice dashboard."} />

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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label} className="p-5">
            <div className="text-sm text-slate-500">{s.label}</div>
            <div className="mt-1 text-3xl font-semibold tabular-nums">{s.value}</div>
            <div className="text-xs text-slate-500">{s.sub}</div>
          </Card>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Card className="p-6">
          <h2 className="font-semibold">Quick start</h2>
          {d.quick_start ? (
            <>
              <p className="mt-3 font-medium">{d.quick_start.title}</p>
              <p className="text-sm text-slate-500">{d.quick_start.topic} · {d.quick_start.difficulty} · {d.quick_start.segments} segments {minutes(d.quick_start.estimated_duration) && `· ${minutes(d.quick_start.estimated_duration)}`}</p>
              <Button className="mt-5" onClick={() => quickStart(d.quick_start!.id)} loading={starting}><PlayCircle className="size-4" /> Start dialogue</Button>
            </>
          ) : <p className="mt-3 text-sm text-slate-500">No dialogues are available yet.</p>}
          <div className="mt-6 flex flex-col gap-2 border-t border-slate-100 pt-4 text-sm">
            <Link href="/dialogues" className="inline-flex items-center gap-1 text-brand-600 hover:underline">Browse the dialogue library <ArrowRight className="size-4" /></Link>
            <Link href="/mock-tests" className="inline-flex items-center gap-1 text-brand-600 hover:underline"><ClipboardCheck className="size-4" /> Take a full mock test</Link>
          </div>
        </Card>
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4">
            <h2 className="font-semibold">Recent attempts</h2>
            <Link href="/attempts" className="text-sm text-brand-600 hover:underline">All attempts</Link>
          </div>
          {d.recent.length === 0 ? <p className="px-5 pb-5 text-sm text-slate-500">Your finished attempts will appear here.</p>
            : <div className="divide-y divide-slate-100 border-t border-slate-100">{d.recent.map((a) => <AttemptRow key={a.id} a={a} />)}</div>}
        </Card>
      </div>
    </>
  );
}
