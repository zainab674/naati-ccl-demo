"use client";

import { useEffect, useState } from "react";

import AttemptRow from "@/components/AttemptRow";
import { Card, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { AttemptSummary } from "@/lib/student";

export default function AttemptsPage() {
  const [rows, setRows] = useState<AttemptSummary[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<AttemptSummary[]>("/attempts").then(setRows).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!rows) return <Spinner />;
  return (
    <>
      <PageHeader title="My attempts" subtitle="Practice dialogues and mock tests, newest first." />
      <Card className="overflow-hidden">
        {rows.length === 0 ? <p className="p-6 text-sm text-slate-500">No attempts yet.</p>
          : <div className="divide-y divide-slate-100">{rows.map((a) => <AttemptRow key={a.id} a={a} />)}</div>}
      </Card>
    </>
  );
}
