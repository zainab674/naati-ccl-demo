"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Card, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

type Item = { segment_attempt_id: string; attempt_id: string; student: string; dialogue: string; segment_number: number;
  scoring_status: string; reason: string; submitted_at: string | null };

export default function ReviewQueue() {
  const [rows, setRows] = useState<Item[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Item[]>("/admin/review-queue").then(setRows).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!rows) return <Spinner />;
  return (
    <>
      <PageHeader title="Review queue" subtitle="Segments flagged by scoring: low confidence, pronunciation, no speech, or scoring failures." />
      <Card className="overflow-hidden">
        <ul className="divide-y divide-slate-100">
          {rows.map((r) => (
            <li key={r.segment_attempt_id}>
              <Link href={`/admin/attempts/${r.attempt_id}#seg-${r.segment_attempt_id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm hover:bg-slate-50">
                <span><span className="font-medium">{r.student}</span> · {r.dialogue} · segment {r.segment_number}</span>
                <span className="flex items-center gap-3">
                  <span className="text-slate-500">{r.reason}</span>
                  {r.scoring_status === "Failed" && <Badge tone="red">Failed</Badge>}
                  <span className="text-xs text-slate-400">{r.submitted_at ? fmtDateTime(r.submitted_at) : ""}</span>
                </span>
              </Link>
            </li>
          ))}
          {rows.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">Nothing to review.</li>}
        </ul>
      </Card>
    </>
  );
}
