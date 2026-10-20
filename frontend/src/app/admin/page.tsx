"use client";

import { Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Card, ErrorNote, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

type Overview = {
  students: number; active_students: number; dialogues_published: number; dialogues_total: number; courses: number;
  attempts: number; segments_needing_review: number; emails_failed: number;
  recent_imports: { id: string; type: string; file_name: string; status: string; created_at: string }[];
};

export default function AdminOverview() {
  const [o, setO] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Overview>("/admin/overview").then(setO).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!o) return <Spinner />;

  const stats = [
    { label: "Students", value: o.students, sub: `${o.active_students} with an active plan`, href: "/admin/students" },
    { label: "Dialogues", value: o.dialogues_published, sub: `${o.dialogues_total} in total`, href: "/admin/dialogues" },
    { label: "Dialogue attempts", value: o.attempts, sub: "all time", href: "/admin/students" },
    { label: "Segments to review", value: o.segments_needing_review, sub: "flagged by scoring", href: "/admin/review" },
  ];
  return (
    <>
      <PageHeader title="Admin" subtitle="Content, students and scoring review." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Link key={s.label} href={s.href}>
            <Card className="p-5 transition-shadow hover:shadow-md">
              <div className="text-sm text-slate-500">{s.label}</div>
              <div className="mt-1 text-3xl font-semibold tabular-nums">{s.value}</div>
              <div className="mt-1 text-xs text-slate-500">{s.sub}</div>
            </Card>
          </Link>
        ))}
      </div>
      {o.emails_failed > 0 && <div className="mt-6"><ErrorNote>{o.emails_failed} email(s) failed to send. Check the email provider settings.</ErrorNote></div>}
      <Card className="mt-8 p-6">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Recent imports</h2>
          <LinkButton href="/admin/imports" variant="secondary"><Upload className="size-4" /> Import CSV</LinkButton>
        </div>
        {o.recent_imports.length === 0 ? <p className="mt-3 text-sm text-slate-500">No imports yet.</p> : (
          <ul className="mt-3 divide-y divide-slate-100 text-sm">
            {o.recent_imports.map((j) => (
              <li key={j.id}>
                <Link href={`/admin/imports/${j.id}`} className="-mx-2 flex items-center justify-between rounded px-2 py-2 hover:bg-slate-50">
                  <span>{j.file_name} <span className="text-slate-400">({j.type})</span></span>
                  <span className="flex items-center gap-3"><Badge>{j.status}</Badge><span className="text-xs text-slate-400">{fmtDateTime(j.created_at)}</span></span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
