"use client";

import { AlertTriangle, Eye } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Card, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

type Row = {
  id: string; student: string; student_email: string; flagged: boolean; mode: string; titles: string[]; status: string;
  started_at: string; tab_blurs: number; needs_review: number; total: number | null; total_max: number | null;
  passed: boolean | null; reviewed: boolean;
};

export default function Submissions() {
  const [rows, setRows] = useState<Row[] | null>(null);
  useEffect(() => { api<Row[]>("/admin/attempts").then(setRows); }, []);
  return (
    <div>
      <PageHeader title="Submissions" subtitle="Every attempt, with its AI score. Open one to hear the recordings, read the model's reasoning and override." />
      <Card>
        {!rows ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th className="py-3 pl-5 pr-4">Student</th><th className="py-3 pr-4">Activity</th><th className="py-3 pr-4">Date</th>
                  <th className="py-3 pr-4">Score</th><th className="py-3 pr-4">Status</th><th className="py-3 pr-4">Integrity</th><th className="py-3 pr-5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/60">
                    <td className="py-3.5 pl-5 pr-4">
                      <div className="font-medium">{r.student} {r.flagged && <Badge tone="red">flagged</Badge>}</div>
                      <div className="text-xs text-slate-500">{r.student_email}</div>
                    </td>
                    <td className="py-3.5 pr-4">
                      <Badge tone={r.mode === "mock" ? "violet" : "brand"}>{r.mode === "mock" ? "Mock" : "Practice"}</Badge>
                      <div className="mt-1 text-slate-600">{r.titles.join(" + ")}</div>
                    </td>
                    <td className="py-3.5 pr-4 text-slate-500">{fmtDateTime(r.started_at)}</td>
                    <td className="py-3.5 pr-4 tabular-nums">
                      {r.total !== null ? <><span className="font-semibold">{r.total}</span><span className="text-slate-400">/{r.total_max}</span>
                        <span className={r.passed ? "ml-2 text-xs text-emerald-600" : "ml-2 text-xs text-rose-600"}>{r.passed ? "pass" : "fail"}</span></> : ""}
                    </td>
                    <td className="py-3.5 pr-4">
                      <div className="flex flex-wrap gap-1">
                        {r.status === "in_progress" ? <Badge tone="amber">In progress</Badge> : r.reviewed ? <Badge tone="green">Reviewed</Badge> : <Badge>AI marked</Badge>}
                        {r.needs_review > 0 && <Badge tone="amber"><AlertTriangle className="size-3" />{r.needs_review} to review</Badge>}
                      </div>
                    </td>
                    <td className="py-3.5 pr-4 text-xs text-slate-500">{r.tab_blurs ? `${r.tab_blurs} tab switch${r.tab_blurs > 1 ? "es" : ""}` : ""}</td>
                    <td className="py-3.5 pr-5 text-right">
                      {r.status !== "in_progress" && (
                        <Link href={`/admin/attempts/${r.id}`} className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-brand-600 hover:bg-brand-50">
                          <Eye className="size-4" /> Review
                        </Link>
                      )}
                    </td>
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
