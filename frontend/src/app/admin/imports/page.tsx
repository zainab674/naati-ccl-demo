"use client";

import { Download, Upload } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import ImportReport, { type ImportJob, statusTone } from "@/components/ImportReport";
import { Badge, Button, Card, cx, ErrorNote, PageHeader } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

const KINDS = [
  { id: "dialogues", label: "Dialogues", help: "One row per Meaning Unit. Dialogue and segment columns repeat on each row." },
  { id: "courses", label: "Courses", help: "One row per lesson." },
] as const;

export default function ImportsPage() {
  const [kind, setKind] = useState<"dialogues" | "courses">("dialogues");
  const [file, setFile] = useState<File | null>(null);
  const [checkUrls, setCheckUrls] = useState(true);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [busy, setBusy] = useState<"" | "upload" | "commit">("");
  const [error, setError] = useState("");

  const loadJobs = () => api<ImportJob[]>("/admin/imports").then(setJobs).catch(() => {});
  useEffect(() => { loadJobs(); }, []);

  const validate = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy("upload");
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("check_urls", String(checkUrls));
    try {
      setJob(await api<ImportJob>(`/admin/imports/${kind}`, { method: "POST", body: fd }));
      loadJobs();
    } catch (err) { setError((err as Error).message); }
    setBusy("");
  };

  const commit = async () => {
    if (!job) return;
    setBusy("commit");
    setError("");
    try {
      const done = await api<ImportJob>(`/admin/imports/${job.id}/commit`, { method: "POST" });
      setJob(done);
      loadJobs();
    } catch (err) { setError((err as Error).message); }
    setBusy("");
  };

  const help = KINDS.find((k) => k.id === kind)!.help;
  return (
    <>
      <PageHeader title="CSV import" subtitle="Upload a file, review the validation report, then commit. Re-importing a file updates by key and never duplicates." />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Card className="p-6">
          <div className="flex gap-2">
            {KINDS.map((k) => (
              <button key={k.id} onClick={() => { setKind(k.id); setJob(null); }}
                className={cx("rounded-lg px-3 py-1.5 text-sm font-medium", kind === k.id ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200")}>
                {k.label}
              </button>
            ))}
          </div>
          <p className="mt-3 text-sm text-slate-600">{help}</p>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <a href={`/api/admin/imports/templates/${kind}-template.csv`} className="inline-flex items-center gap-1 text-brand-600 hover:underline"><Download className="size-4" /> Template</a>
            <a href={`/api/admin/imports/templates/${kind}-sample.csv`} className="inline-flex items-center gap-1 text-brand-600 hover:underline"><Download className="size-4" /> Sample</a>
          </div>
          <form onSubmit={validate} className="mt-6 space-y-4">
            <input type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setJob(null); }}
              className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200" />
            {kind === "dialogues" && (
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={checkUrls} onChange={(e) => setCheckUrls(e.target.checked)} className="accent-brand-600" />
                Check that every audio and waveform URL is reachable
              </label>
            )}
            <Button type="submit" disabled={!file} loading={busy === "upload"}><Upload className="size-4" /> Validate (dry run)</Button>
          </form>
          {error && <div className="mt-4"><ErrorNote>{error}</ErrorNote></div>}
        </Card>

        <div>
          {job ? (
            <>
              <ImportReport job={job} />
              {job.status === "Validated" && (
                <div className="mt-4 flex items-center justify-between rounded-xl bg-brand-50 p-4">
                  <span className="text-sm text-brand-900">No errors. Commit to write these records{kind === "dialogues" ? " and start audio processing" : ""}.</span>
                  <Button onClick={commit} loading={busy === "commit"}>Commit import</Button>
                </div>
              )}
              {job.committed_at && <Link href={`/admin/imports/${job.id}`} className="mt-4 inline-block text-sm text-brand-600 hover:underline">Follow progress</Link>}
            </>
          ) : (
            <Card className="p-6 text-sm text-slate-500">The validation report appears here.</Card>
          )}
        </div>
      </div>

      <Card className="mt-8 overflow-hidden">
        <div className="px-6 py-4 font-semibold">History</div>
        <table className="w-full text-sm">
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-t border-slate-100">
                <td className="px-6 py-2"><Link href={`/admin/imports/${j.id}`} className="hover:underline">{j.file_name}</Link></td>
                <td className="px-2 py-2 capitalize text-slate-500">{j.type}</td>
                <td className="px-2 py-2"><Badge tone={statusTone(j.status)}>{j.status}</Badge></td>
                <td className="px-6 py-2 text-right text-xs text-slate-400">{fmtDateTime(j.created_at)}</td>
              </tr>
            ))}
            {jobs.length === 0 && <tr><td className="px-6 py-4 text-slate-500">No imports yet.</td></tr>}
          </tbody>
        </table>
      </Card>
    </>
  );
}
