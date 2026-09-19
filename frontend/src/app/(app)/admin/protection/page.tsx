"use client";

import { CheckCircle2, Clock, FileLock2, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Card, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

type P = {
  controls: { name: string; status: "on" | "planned"; detail: string }[];
  sample: null | { dialogue: string; files: string[]; encrypted: boolean; segment_count: number; plain_audio_files_on_server: number };
  grants_24h: number;
  events_24h: Record<string, number>;
  flagged_users: { name: string; email: string }[];
  recent_events: { kind: string; detail: string; user: string; ip: string; at: string }[];
};

const KIND: Record<string, string> = {
  no_session: "No login cookie", session_mismatch: "Link used in another session", bad_or_expired_signature: "Expired or tampered link",
  wrong_owner: "Not the attempt owner", rate_limited: "Rate limit hit", key_refetch: "Key requested too often",
  account_flagged: "Account flagged", bad_path: "Probing unknown file",
};

export default function Protection() {
  const [p, setP] = useState<P | null>(null);
  const load = useCallback(() => api<P>("/admin/protection").then(setP), []);
  useEffect(() => { load(); }, [load]);
  if (!p) return <Spinner />;
  const blocked = Object.values(p.events_24h).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Content protection" subtitle="What stops the test audio being downloaded and resold, and what the system has blocked."
        actions={<Button variant="secondary" size="sm" onClick={load}><RefreshCw className="size-4" /> Refresh</Button>} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5"><div className="text-sm text-slate-500">Plays authorised (24h)</div><div className="mt-2 text-3xl font-semibold tabular-nums">{p.grants_24h}</div></Card>
        <Card className="p-5"><div className="text-sm text-slate-500">Requests blocked (24h)</div><div className="mt-2 text-3xl font-semibold tabular-nums">{blocked}</div></Card>
        <Card className="p-5"><div className="text-sm text-slate-500">Flagged accounts</div><div className="mt-2 text-3xl font-semibold tabular-nums">{p.flagged_users.length}</div>
          {p.flagged_users.length > 0 && <button className="mt-1 text-xs text-brand-600 hover:underline" onClick={() => api("/admin/protection/unflag", { method: "POST" }).then(load)}>Clear flags</button>}</Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="border-b border-slate-100 px-5 py-4 font-semibold">Controls</div>
          <ul className="divide-y divide-slate-100">
            {p.controls.map((c) => (
              <li key={c.name} className="flex gap-3 px-5 py-3.5">
                {c.status === "on" ? <ShieldCheck className="mt-0.5 size-5 shrink-0 text-emerald-600" /> : <Clock className="mt-0.5 size-5 shrink-0 text-amber-500" />}
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-sm font-medium">{c.name}
                    {c.status === "on" ? <Badge tone="green">On</Badge> : <Badge tone="amber">Planned, not in demo</Badge>}</div>
                  <div className="text-sm text-slate-500">{c.detail}</div>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <div className="space-y-6">
          {p.sample && (
            <Card className="p-5">
              <div className="flex items-center gap-2 font-semibold"><FileLock2 className="size-5 text-brand-600" /> What&apos;s actually on the server</div>
              <p className="mt-1 text-sm text-slate-500">Segment 1 of <b>{p.sample.dialogue}</b>, as stored:</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {p.sample.files.filter((f) => !f.startsWith(".")).map((f) => <code key={f} className="rounded bg-slate-100 px-2 py-1 text-xs">{f}</code>)}
              </div>
              <ul className="mt-4 space-y-1.5 text-sm">
                <li className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-600" /> {p.sample.segment_count} encrypted chunks, {p.sample.encrypted ? "AES-128" : "NOT encrypted"}</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-600" /> {p.sample.plain_audio_files_on_server} plain mp3/wav files anywhere in the media store</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-600" /> Key file never served without a signed, session-bound URL</li>
              </ul>
            </Card>
          )}
          <Card className="p-5">
            <div className="flex items-center gap-2 font-semibold"><ShieldAlert className="size-5 text-amber-500" /> Try it yourself</div>
            <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-slate-600">
              <li>Sign in as a student and start any dialogue.</li>
              <li>Open DevTools → Network while a segment plays. You&apos;ll see <code>.ts</code> chunks, not an mp3.</li>
              <li>Copy a chunk or playlist URL into a private window. It&apos;s refused because there&apos;s no session.</li>
              <li>Paste it into another logged-in browser. It&apos;s refused because the session doesn&apos;t match.</li>
              <li>Wait 5 minutes and retry in the same tab. The link has expired.</li>
              <li>Refresh this page. Each attempt appears below.</li>
            </ol>
            <p className="mt-3 text-xs text-slate-400">Someone can still record audio from their soundcard while it plays. Per-user watermarking (planned) makes that recording traceable to the account it came from.</p>
          </Card>
        </div>
      </div>

      <Card>
        <div className="border-b border-slate-100 px-5 py-4 font-semibold">Blocked requests</div>
        {p.recent_events.length === 0 ? <div className="px-5 py-8 text-center text-sm text-slate-500">Nothing blocked yet.</div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2.5 pl-5 pr-4">When</th><th className="py-2.5 pr-4">What</th><th className="py-2.5 pr-4">Account</th><th className="py-2.5 pr-5">Detail</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {p.recent_events.map((e, i) => (
                  <tr key={i}>
                    <td className="py-2.5 pl-5 pr-4 text-slate-500">{fmtDateTime(e.at)}</td>
                    <td className="py-2.5 pr-4"><Badge tone={e.kind === "account_flagged" || e.kind === "rate_limited" ? "red" : "amber"}>{KIND[e.kind] ?? e.kind}</Badge></td>
                    <td className="py-2.5 pr-4">{e.user}</td>
                    <td className="max-w-md truncate py-2.5 pr-5 font-mono text-xs text-slate-500">{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
