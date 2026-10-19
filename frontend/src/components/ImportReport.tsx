"use client";

import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

import { Badge, Card } from "./ui";

export type ImportJob = {
  id: string; type: "dialogues" | "courses"; file_name: string; status: string; error: string;
  report: {
    ok: boolean; error_count: number; warning_count: number; check_urls?: boolean;
    errors: { row: number | null; column: string; message: string }[];
    warnings: { row: number | null; column: string; message: string }[];
    summary: Record<string, number>;
  };
  counts: Record<string, number>;
  progress: { media_total?: number; media_done?: number; media_failed?: number; failures?: { segment: string; error: string }[] };
  created_at: string; committed_at: string | null;
};

const label = (k: string) => k.replace(/_/g, " ");

export const statusTone = (s: string) =>
  s === "Completed" || s === "Validated" ? "green" : s === "Invalid" || s === "Failed" ? "red" : "amber";

export default function ImportReport({ job }: { job: ImportJob }) {
  const r = job.report;
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-medium">
            {r.ok ? <CheckCircle2 className="size-5 text-emerald-600" /> : <XCircle className="size-5 text-rose-600" />}
            {job.file_name}
          </div>
          <Badge tone={statusTone(job.status)}>{job.status}</Badge>
        </div>
        {r.summary && Object.keys(r.summary).length > 0 && (
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {Object.entries(r.summary).map(([k, v]) => (
              <div key={k}><dt className="text-xs capitalize text-slate-500">{label(k)}</dt><dd className="font-semibold tabular-nums">{v}</dd></div>
            ))}
          </dl>
        )}
        {r.check_urls === false && <p className="mt-3 text-xs text-amber-700">URL reachability was not checked for this file.</p>}
        {job.error && <p className="mt-3 text-sm text-rose-700">{job.error}</p>}
        {Object.keys(job.counts ?? {}).length > 0 && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Committed</div>
            <dl className="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {Object.entries(job.counts).map(([k, v]) => (
                <div key={k}><dt className="text-xs capitalize text-slate-500">{label(k)}</dt><dd className="font-semibold tabular-nums">{v}</dd></div>
              ))}
            </dl>
          </div>
        )}
        {(job.progress?.media_total ?? 0) > 0 && (
          <div className="mt-4 border-t border-slate-100 pt-4 text-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Audio processing</div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full bg-brand-500 transition-[width]" style={{ width: `${(100 * ((job.progress.media_done ?? 0) + (job.progress.media_failed ?? 0))) / job.progress.media_total!}%` }} />
            </div>
            <p className="mt-1 text-slate-600">
              {job.progress.media_done ?? 0} of {job.progress.media_total} segments ready
              {(job.progress.media_failed ?? 0) > 0 && <span className="text-rose-700">, {job.progress.media_failed} failed</span>}
            </p>
            {job.progress.failures?.map((f) => <p key={f.segment} className="mt-1 text-xs text-rose-700">{f.segment}: {f.error}</p>)}
          </div>
        )}
      </Card>
      {r.errors?.length > 0 && <Issues title={`Errors (${r.error_count})`} items={r.errors} tone="error" />}
      {r.warnings?.length > 0 && <Issues title={`Warnings (${r.warning_count})`} items={r.warnings} tone="warning" />}
    </div>
  );
}

function Issues({ title, items, tone }: { title: string; items: ImportJob["report"]["errors"]; tone: "error" | "warning" }) {
  return (
    <Card className="overflow-hidden">
      <div className={tone === "error" ? "flex items-center gap-2 bg-rose-50 px-5 py-3 text-sm font-semibold text-rose-800" : "flex items-center gap-2 bg-amber-50 px-5 py-3 text-sm font-semibold text-amber-800"}>
        <AlertTriangle className="size-4" /> {title}
      </div>
      <div className="max-h-96 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-5 py-2">Row</th><th className="px-2 py-2">Column</th><th className="px-2 py-2">Problem</th></tr>
          </thead>
          <tbody>
            {items.map((e, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-5 py-2 tabular-nums text-slate-500">{e.row ?? "-"}</td>
                <td className="px-2 py-2 font-mono text-xs">{e.column}</td>
                <td className="px-2 py-2">{e.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
