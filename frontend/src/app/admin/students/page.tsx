"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Card, ErrorNote, inputClass, PageHeader, Spinner } from "@/components/ui";
import { subTone } from "@/lib/admin";
import { api, fmtDate } from "@/lib/api";

type Row = { id: string; name: string; email: string; subscription_status: string; created_at: string; last_login_at: string | null;
  dialogue_attempts: number; average_dialogue_score: number | null; last_attempt_at: string | null; flagged: boolean };


export default function AdminStudents() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const t = setTimeout(() => api<Row[]>(`/admin/students?q=${encodeURIComponent(q)}&status=${status}`).then(setRows).catch((e) => setError(e.message)), 200);
    return () => clearTimeout(t);
  }, [q, status]);

  return (
    <>
      <PageHeader title="Students" subtitle="Profiles, subscription status, attempts and scores." />
      <div className="mb-4 flex flex-wrap gap-3">
        <input placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} className={`${inputClass} mt-0 !w-72`} />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={`${inputClass} mt-0 !w-44`}>
          <option value="">Any subscription</option><option>Active</option><option>Trial</option><option>Expired</option><option>Inactive</option>
        </select>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="px-5 py-3">Student</th><th>Subscription</th><th>Attempts</th><th>Avg dialogue</th><th>Last attempt</th><th>Joined</th></tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-5 py-3"><Link href={`/admin/students/${s.id}`} className="font-medium hover:underline">{s.name}</Link>
                    <div className="text-xs text-slate-500">{s.email}{s.flagged && <Badge tone="red" className="ml-2">Flagged</Badge>}</div></td>
                  <td><Badge tone={subTone(s.subscription_status)}>{s.subscription_status}</Badge></td>
                  <td className="tabular-nums">{s.dialogue_attempts}</td>
                  <td className="tabular-nums">{s.average_dialogue_score ?? "–"}</td>
                  <td>{s.last_attempt_at ? fmtDate(s.last_attempt_at) : "–"}</td>
                  <td>{fmtDate(s.created_at)}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={6} className="px-5 py-6 text-slate-500">No students found.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
