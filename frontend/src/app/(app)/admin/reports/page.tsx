"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Card, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

type R = { id: string; student: string; activity: string; text: string; status: string; created_at: string };

export default function Reports() {
  const [rows, setRows] = useState<R[] | null>(null);
  const load = useCallback(() => api<R[]>("/admin/reports").then(setRows), []);
  useEffect(() => { load(); }, [load]);
  return (
    <div>
      <PageHeader title="Issue reports" subtitle="Problems students flagged on individual dialogues." />
      <Card>
        {!rows ? <Spinner /> : rows.length === 0 ? <div className="py-12 text-center text-sm text-slate-500">No reports.</div> : (
          <ul className="divide-y divide-slate-100">
            {rows.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start gap-4 px-5 py-4">
                <div className="flex-1">
                  <div className="text-sm font-medium">{r.activity}</div>
                  <p className="mt-0.5 text-sm text-slate-600">{r.text}</p>
                  <div className="mt-1 text-xs text-slate-400">{r.student} · {fmtDateTime(r.created_at)}</div>
                </div>
                {r.status === "open" ? (
                  <Button size="sm" variant="secondary" onClick={() => api(`/admin/reports/${r.id}/resolve`, { method: "POST" }).then(load)}>Mark resolved</Button>
                ) : <Badge tone="green">Resolved</Badge>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
