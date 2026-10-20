"use client";

import { ClipboardCheck, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Card, DifficultyBadge, ErrorNote, inputClass, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api, fetchLanguages, type Language } from "@/lib/api";

type DialogueRow = {
  id: string; key: string; title: string; topic: string | null; difficulty: string; status: string; is_free: boolean;
  version: number; segments: number; meaning_units: number; media_ready: number; media_failed: number;
  estimated_duration: number | null; language_name: string;
};


export default function AdminDialogues() {
  const router = useRouter();
  const [rows, setRows] = useState<DialogueRow[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [language, setLanguage] = useState("");
  const [languages, setLanguages] = useState<Language[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { fetchLanguages().then(setLanguages).catch(() => {}); }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      api<DialogueRow[]>(`/admin/dialogues?q=${encodeURIComponent(q)}&status=${status}&language=${language}`).then(setRows).catch((e) => setError(e.message));
    }, 200);
    return () => clearTimeout(t);
  }, [q, status, language]);

  return (
    <>
      <PageHeader title="Dialogues" subtitle="Imported dialogues start as Draft. Publish when the audio is ready."
        actions={<div className="flex gap-2"><LinkButton href="/admin/mock-tests" variant="secondary"><ClipboardCheck className="size-4" /> Mock tests</LinkButton><LinkButton href="/admin/imports"><Upload className="size-4" /> Import CSV</LinkButton></div>} />
      <div className="mb-4 flex flex-wrap gap-3">
        <input placeholder="Search title or key" value={q} onChange={(e) => setQ(e.target.value)} className={`${inputClass} mt-0 !w-72`} />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={`${inputClass} mt-0 !w-44`}>
          <option value="">All statuses</option><option>Draft</option><option>Published</option><option>Archived</option>
        </select>
        <select value={language} onChange={(e) => setLanguage(e.target.value)} className={`${inputClass} mt-0 !w-44`}>
          <option value="">All languages</option>
          {languages.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
        </select>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="px-5 py-3">Dialogue</th><th>Language</th><th>Topic</th><th>Difficulty</th><th>Segments / MUs</th><th>Audio</th><th>Status</th></tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id} onClick={() => router.push(`/admin/dialogues/${d.id}`)} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-5 py-3">
                    <Link href={`/admin/dialogues/${d.id}`} className="font-medium hover:underline">{d.title}</Link>
                    <div className="font-mono text-xs text-slate-400">{d.key} · v{d.version}</div>
                  </td>
                  <td>{d.language_name}</td>
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
