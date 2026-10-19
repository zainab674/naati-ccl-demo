"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Card, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { subTone } from "@/lib/admin";
import { api, fmtDate, fmtDateTime } from "@/lib/api";
import type { AttemptSummary } from "@/lib/student";

type Student = {
  id: string; name: string; email: string; subscription_status: string; stripe_customer_id: string | null;
  target_exam_date: string | null; created_at: string; last_login_at: string | null; flagged: boolean; lessons_completed: number;
  subscriptions: { plan: string | null; status: string; stripe_subscription_id: string | null; current_period_end: string | null; cancel_at_period_end: boolean }[];
  payments: { amount: number; currency: string; status: string; receipt_url: string; created_at: string }[];
  attempts: AttemptSummary[];
};

export default function AdminStudent() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<Student | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Student>(`/admin/students/${id}`).then(setS).catch((e) => setError(e.message)); }, [id]);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!s) return <Spinner />;
  return (
    <>
      <PageHeader title={s.name} subtitle={<>{s.email} · <Link href="/admin/students" className="text-brand-600 hover:underline">All students</Link></>} />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
        <div className="space-y-6">
          <Card className="space-y-2 p-6 text-sm">
            <div className="flex justify-between"><span className="text-slate-500">Subscription</span><Badge tone={subTone(s.subscription_status)}>{s.subscription_status}</Badge></div>
            <div className="flex justify-between"><span className="text-slate-500">Joined</span><span>{fmtDate(s.created_at)}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Last login</span><span>{s.last_login_at ? fmtDateTime(s.last_login_at) : "–"}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Target exam</span><span>{s.target_exam_date ? fmtDate(s.target_exam_date) : "–"}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Lessons completed</span><span>{s.lessons_completed}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Stripe customer</span><span className="font-mono text-xs">{s.stripe_customer_id ?? "–"}</span></div>
            {s.flagged && <Badge tone="red">Flagged by content protection</Badge>}
          </Card>
          <Card className="p-6">
            <h2 className="font-semibold">Subscriptions and payments</h2>
            {s.subscriptions.map((x, i) => (
              <div key={i} className="mt-3 text-sm">{x.plan ?? "Plan"} · {x.status}{x.current_period_end && ` · until ${fmtDate(x.current_period_end)}`}{x.cancel_at_period_end && " (cancels)"}</div>
            ))}
            {s.payments.map((p, i) => (
              <div key={i} className="mt-2 flex justify-between text-sm text-slate-600">
                <span>{fmtDate(p.created_at)} · ${(p.amount / 100).toFixed(2)} {p.currency.toUpperCase()}</span>
                {p.receipt_url && <a href={p.receipt_url} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">Receipt</a>}
              </div>
            ))}
            {!s.subscriptions.length && !s.payments.length && <p className="mt-2 text-sm text-slate-500">No payments yet.</p>}
          </Card>
        </div>
        <Card className="overflow-hidden">
          <div className="px-5 py-4 font-semibold">Attempts</div>
          <ul className="divide-y divide-slate-100 border-t border-slate-100">
            {s.attempts.map((a) => (
              <li key={a.id}>
                <Link href={`/admin/attempts/${a.id}`} className="flex items-center justify-between gap-3 px-5 py-3 text-sm hover:bg-slate-50">
                  <span><span className="font-medium">{a.title}</span><span className="ml-2 text-slate-500">{a.kind === "mock" ? "Mock" : "Practice"} · {a.started_at ? fmtDate(a.started_at) : ""}</span></span>
                  <span className="flex items-center gap-2 tabular-nums">
                    {a.status === "In Progress" ? <Badge tone="amber">In progress</Badge> : a.total_score !== null ? `${a.total_score}/${a.maximum_score}` : <Badge>{a.scoring_status}</Badge>}
                    {a.result && <Badge tone={a.result === "Pass" ? "green" : "red"}>{a.result}</Badge>}
                  </span>
                </Link>
              </li>
            ))}
            {!s.attempts.length && <li className="px-5 py-4 text-sm text-slate-500">No attempts yet.</li>}
          </ul>
        </Card>
      </div>
    </>
  );
}
