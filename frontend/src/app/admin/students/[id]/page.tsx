"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Card, ErrorNote, Field, inputClass, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { subTone } from "@/lib/admin";
import { api, fetchLanguages, fmtDate, fmtDateTime, type Language } from "@/lib/api";
import type { AttemptSummary } from "@/lib/student";

type Student = {
  id: string; name: string; first_name: string; last_name: string; email: string; subscription_status: string;
  stripe_customer_id: string | null; access_expires_at: string | null; language: string | null; is_active: boolean;
  enrolled_by: string | null; stripe_managed: boolean; access_is_manual: boolean;
  target_exam_date: string | null; created_at: string; last_login_at: string | null; flagged: boolean; lessons_completed: number;
  subscriptions: { plan: string | null; status: string; source: string; note: string; granted_by: string | null; created_at: string;
    stripe_subscription_id: string | null; current_period_end: string | null; cancel_at_period_end: boolean }[];
  payments: { amount: number; currency: string; status: string; receipt_url: string; created_at: string }[];
  attempts: AttemptSummary[];
};

type Msg = { ok: boolean; text: string } | null;

const MANUAL_LABEL: Record<string, string> = { active: "Active access granted", trialing: "Trial access granted", revoked: "Access removed" };

export default function AdminStudent() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<Student | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => api<Student>(`/admin/students/${id}`).then(setS).catch((e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);
  if (error && !s) return <ErrorNote>{error}</ErrorNote>;
  if (!s) return <Spinner />;
  return (
    <>
      <PageHeader title={s.name} subtitle={<>{s.email} · <Link href="/admin/students" className="text-brand-600 hover:underline">All students</Link></>} />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
        <div className="space-y-6">
          <Card className="space-y-2 p-6 text-sm">
            <div className="flex justify-between"><span className="text-slate-500">Access</span>
              <span><Badge tone={subTone(s.subscription_status)}>{s.subscription_status}</Badge>
                {s.access_expires_at && <span className="ml-2 text-slate-500">until {fmtDate(s.access_expires_at)}</span>}</span></div>
            {!s.is_active && <div className="flex justify-between"><span className="text-slate-500">Account</span><Badge>Deactivated</Badge></div>}
            {s.enrolled_by && <div className="flex justify-between"><span className="text-slate-500">Enrolled by</span><span>{s.enrolled_by}</span></div>}
            <div className="flex justify-between"><span className="text-slate-500">Joined</span><span>{fmtDate(s.created_at)}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Last login</span><span>{s.last_login_at ? fmtDateTime(s.last_login_at) : "–"}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Target exam</span><span>{s.target_exam_date ? fmtDate(s.target_exam_date) : "–"}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Lessons completed</span><span>{s.lessons_completed}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Stripe customer</span><span className="font-mono text-xs">{s.stripe_customer_id ?? "–"}</span></div>
            {s.flagged && <Badge tone="red">Flagged by content protection</Badge>}
          </Card>
          <AccessCard key={`access-${s.subscription_status}-${s.access_expires_at}`} s={s} onSaved={load} />
          <Card className="p-6">
            <h2 className="font-semibold">Access history and payments</h2>
            {s.subscriptions.map((x, i) => (
              <div key={i} className="mt-3 text-sm">
                {x.source === "manual" ? <><Badge tone="violet">Teacher</Badge> {MANUAL_LABEL[x.status] ?? x.status}</> : <>{x.plan ?? "Plan"} · {x.status}</>}
                {x.current_period_end && ` · until ${fmtDate(x.current_period_end)}`}{x.cancel_at_period_end && " (cancels)"}
                {x.source === "manual" && <div className="text-xs text-slate-500">{fmtDateTime(x.created_at)}{x.granted_by && ` by ${x.granted_by}`}{x.note && ` · ${x.note}`}</div>}
              </div>
            ))}
            {s.payments.map((p, i) => (
              <div key={i} className="mt-2 flex justify-between text-sm text-slate-600">
                <span>{fmtDate(p.created_at)} · ${(p.amount / 100).toFixed(2)} {p.currency.toUpperCase()}</span>
                {p.receipt_url && <a href={p.receipt_url} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">Receipt</a>}
              </div>
            ))}
            {!s.subscriptions.length && !s.payments.length && <p className="mt-2 text-sm text-slate-500">No access granted or payments yet.</p>}
          </Card>
          <AccountCard s={s} onSaved={load} />
        </div>
        <Card className="h-fit overflow-hidden">
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

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null;
  return msg.ok ? <SuccessNote>{msg.text}</SuccessNote> : <ErrorNote>{msg.text}</ErrorNote>;
}

function AccessCard({ s, onSaved }: { s: Student; onSaved: () => void }) {
  const current = s.subscription_status === "Active" || s.subscription_status === "Trial" ? s.subscription_status : "None";
  const [access, setAccess] = useState(current);
  const [until, setUntil] = useState(s.access_expires_at ? s.access_expires_at.slice(0, 10) : "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api(`/admin/students/${s.id}/access`, { method: "POST", json: { access, access_until: access !== "None" && until ? until : null, note } });
      setMsg({ ok: true, text: "Access updated." });
      onSaved();
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
    setBusy(false);
  };
  return (
    <Card className="space-y-3 p-6">
      <h2 className="font-semibold">Change access</h2>
      {s.stripe_managed && <p className="text-xs text-amber-700">This student pays through Stripe. The next Stripe event (renewal, cancellation) overwrites a change made here.</p>}
      <div className="grid grid-cols-2 gap-3">
        <label className="block"><span className="text-sm font-medium text-slate-700">Access</span>
          <select className={inputClass} value={access} onChange={(e) => setAccess(e.target.value)}>
            <option value="Trial">Trial</option><option value="Active">Active</option><option value="None">None</option>
          </select></label>
        <Field label="Until" type="date" value={until} disabled={access === "None"} onChange={(e) => setUntil(e.target.value)} hint="Empty = no end date." />
      </div>
      <Field label="Note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="E.g. extended until the March exam" />
      <Note msg={msg} />
      <Button size="sm" onClick={save} loading={busy}>Save access</Button>
    </Card>
  );
}

function AccountCard({ s, onSaved }: { s: Student; onSaved: () => void }) {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [first, setFirst] = useState(s.first_name);
  const [last, setLast] = useState(s.last_name);
  const [language, setLanguage] = useState(s.language ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  useEffect(() => { fetchLanguages().then(setLanguages).catch(() => {}); }, []);

  const act = async (key: string, path: string, init: Parameters<typeof api>[1], done: string) => {
    setBusy(key);
    setMsg(null);
    try {
      await api(path, init);
      setMsg({ ok: true, text: done });
      onSaved();
      return true;
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
      return false;
    } finally { setBusy(""); }
  };
  const base = `/admin/students/${s.id}`;
  return (
    <Card className="space-y-3 p-6">
      <h2 className="font-semibold">Account</h2>
      <div className="grid grid-cols-2 gap-3">
        <Field label="First name" value={first} onChange={(e) => setFirst(e.target.value)} />
        <Field label="Last name" value={last} onChange={(e) => setLast(e.target.value)} />
      </div>
      <label className="block"><span className="text-sm font-medium text-slate-700">Language</span>
        <select className={inputClass} value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="">Not set</option>
          {languages.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
        </select></label>
      <Button size="sm" variant="secondary" loading={busy === "save"}
        onClick={() => act("save", base, { method: "PATCH", json: { first_name: first, last_name: last, language: language || null } }, "Saved.")}>Save details</Button>
      <div className="border-t border-slate-100 pt-3">
        <Field label="Set a new password" type="text" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)}
          hint="For demo accounts. Signs the student out of other sessions." />
        <div className="mt-2 flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" disabled={password.length < 8} loading={busy === "pw"}
            onClick={async () => { if (await act("pw", `${base}/password`, { method: "POST", json: { password } }, "Password set.")) setPassword(""); }}>Set password</Button>
          <Button size="sm" variant="secondary" disabled={!s.is_active} loading={busy === "invite"}
            onClick={() => act("invite", `${base}/invite`, { method: "POST" }, `Set-password link emailed to ${s.email}.`)}>Email set-password link</Button>
        </div>
      </div>
      <div className="border-t border-slate-100 pt-3">
        {s.is_active
          ? <Button size="sm" variant="danger" loading={busy === "active"} onClick={() => {
              if (confirm(`Deactivate ${s.email}? They will be signed out and cannot sign in until reactivated.`)) {
                act("active", base, { method: "PATCH", json: { is_active: false } }, "Account deactivated.");
              }
            }}>Deactivate account</Button>
          : <Button size="sm" variant="secondary" loading={busy === "active"}
              onClick={() => act("active", base, { method: "PATCH", json: { is_active: true } }, "Account reactivated.")}>Reactivate account</Button>}
      </div>
      <Note msg={msg} />
    </Card>
  );
}
