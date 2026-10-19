"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Card, DifficultyBadge, ErrorNote, inputClass, PageHeader, Spinner } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api } from "@/lib/api";

type DialogueRow = {
  id: string; key: string; title: string; topic: string | null; difficulty: string; status: string; is_free: boolean;
  version: number; segments: number; meaning_units: number; media_ready: number; media_failed: number;
  estimated_duration: number | null;
};


export default function AdminDialogues() {
  const [rows, setRows] = useState<DialogueRow[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      api<DialogueRow[]>(`/admin/dialogues?q=${encodeURIComponent(q)}&status=${status}`).then(setRows).catch((e) => setError(e.message));
    }, 200);
    return () => clearTimeout(t);
  }, [q, status]);

  return (
    <>
      <PageHeader title="Dialogues" subtitle="Imported dialogues start as Draft. Publish when the audio is ready."
        actions={<div className="flex gap-3 text-sm"><Link href="/admin/mock-tests" className="text-brand-600 hover:underline">Mock tests</Link><Link href="/admin/imports" className="text-brand-600 hover:underline">Import CSV</Link></div>} />
      <div className="mb-4 flex flex-wrap gap-3">
        <input placeholder="Search title or key" value={q} onChange={(e) => setQ(e.target.value)} className={`${inputClass} mt-0 !w-72`} />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={`${inputClass} mt-0 !w-44`}>
          <option value="">All statuses</option><option>Draft</option><option>Published</option><option>Archived</option>
        </select>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="px-5 py-3">Dialogue</th><th>Topic</th><th>Difficulty</th><th>Segments / MUs</th><th>Audio</th><th>Status</th></tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-5 py-3">
                    <Link href={`/admin/dialogues/${d.id}`} className="font-medium hover:underline">{d.title}</Link>
                    <div className="font-mono text-xs text-slate-400">{d.key} · v{d.version}</div>
                  </td>
                  <td>{d.topic}</td>
                  <td><DifficultyBadge level={d.difficulty} /></td>
                  <td className="tabular-nums">{d.segments} / {d.meaning_units}</td>
                  <td>{d.media_failed > 0 ? <Badge tone="red">{d.media_failed} failed</Badge>
                    : <Badge tone={d.media_ready === d.segments ? "green" : "amber"}>{d.media_ready}/{d.segments} ready</Badge>}</td>
                  <td className="space-x-1"><Badge tone={statusTone(d.status)}>{d.status}</Badge>{d.is_free && <Badge tone="brand">Free</Badge>}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={6} className="px-5 py-6 text-slate-500">No dialogues yet. Import a CSV to add some.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
