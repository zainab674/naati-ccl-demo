"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Badge, Button, Card, ErrorNote, Field, PageHeader, SuccessNote } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";

type Billing = {
  subscription_status: string; has_billing_account: boolean;
  subscription: { plan: string | null; status: string; current_period_end: string | null; cancel_at_period_end: boolean } | null;
  payments: { amount: number; currency: string; receipt_url: string; created_at: string }[];
};

export default function AccountPage() {
  const { user, refresh } = useUser();
  const [profile, setProfile] = useState({ first_name: user.first_name, last_name: user.last_name, target_exam_date: user.target_exam_date ?? "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [billing, setBilling] = useState<Billing | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState("");

  useEffect(() => { api<Billing>("/billing/status").then(setBilling).catch(() => {}); }, []);

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setBusy("profile");
    try {
      await api("/me", { method: "PATCH", json: { ...profile, target_exam_date: profile.target_exam_date || null } });
      await refresh();
      setMsg({ ok: "Profile saved." });
    } catch (err) { setMsg({ err: (err as Error).message }); }
    setBusy("");
  };

  const savePassword = async (e: FormEvent) => {
    e.preventDefault();
    setBusy("password");
    try {
      await api("/me/password", { method: "POST", json: pw });
      setPw({ current_password: "", new_password: "" });
      setMsg({ ok: "Password changed. Other devices have been signed out." });
    } catch (err) { setMsg({ err: (err as Error).message }); }
    setBusy("");
  };

  const openPortal = async () => {
    setBusy("portal");
    try {
      const r = await api<{ url: string }>("/billing/portal", { method: "POST" });
      window.location.assign(r.url);
    } catch (err) { setMsg({ err: (err as Error).message }); setBusy(""); }
  };

  const money = (a: number, c: string) => `$${(a / 100).toFixed(2)} ${c.toUpperCase()}`;

  return (
    <div className="max-w-3xl">
      <PageHeader title="Account" subtitle={user.email} />
      {msg.ok && <div className="mb-4"><SuccessNote>{msg.ok}</SuccessNote></div>}
      {msg.err && <div className="mb-4"><ErrorNote>{msg.err}</ErrorNote></div>}

      <Card className="mb-6 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Plan and billing</h2>
            <p className="mt-1 text-sm text-slate-500">
              Status: <Badge tone={user.has_active_plan ? "green" : "slate"}>{user.subscription_status}</Badge>
              {billing?.subscription?.plan && <> · {billing.subscription.plan}</>}
              {billing?.subscription?.current_period_end && <> · {billing.subscription.cancel_at_period_end ? "ends" : "renews"} {fmtDate(billing.subscription.current_period_end)}</>}
            </p>
          </div>
          {billing?.has_billing_account ? (
            <Button variant="secondary" onClick={openPortal} loading={busy === "portal"}>Manage billing</Button>
          ) : !user.has_active_plan && (
            <Link href="/pricing" className="text-sm font-medium text-brand-600 hover:underline">See plans</Link>
          )}
        </div>
        {billing && billing.payments.length > 0 && (
          <table className="mt-5 w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="py-2">Date</th><th>Amount</th><th /></tr></thead>
            <tbody>
              {billing.payments.map((p) => (
                <tr key={p.created_at} className="border-t border-slate-100">
                  <td className="py-2">{fmtDate(p.created_at)}</td><td>{money(p.amount, p.currency)}</td>
                  <td className="text-right">{p.receipt_url && <a href={p.receipt_url} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">Receipt</a>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="mb-6 p-6">
        <h2 className="font-semibold">Profile</h2>
        <form onSubmit={saveProfile} className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="First name" required value={profile.first_name} onChange={(e) => setProfile({ ...profile, first_name: e.target.value })} />
          <Field label="Last name" value={profile.last_name} onChange={(e) => setProfile({ ...profile, last_name: e.target.value })} />
          <Field label="Target exam date" type="date" value={profile.target_exam_date} onChange={(e) => setProfile({ ...profile, target_exam_date: e.target.value })} />
          <div className="flex items-end"><Button type="submit" loading={busy === "profile"}>Save profile</Button></div>
        </form>
      </Card>

      <Card className="p-6">
        <h2 className="font-semibold">Change password</h2>
        <form onSubmit={savePassword} className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="Current password" type="password" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" />
          <Field label="New password" type="password" required minLength={8} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" />
          <div><Button type="submit" loading={busy === "password"}>Change password</Button></div>
        </form>
      </Card>
    </div>
  );
}
