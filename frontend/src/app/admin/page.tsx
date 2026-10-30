"use client";

import { Copy, RefreshCw, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Badge, Button, Card, ErrorNote, inputClass, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

type Overview = {
  students: number; active_students: number; dialogues_published: number; dialogues_total: number; courses: number;
  attempts: number; segments_needing_review: number; emails_failed: number;
  recent_imports: { id: string; type: string; file_name: string; status: string; created_at: string }[];
};

export default function AdminOverview() {
  const { user } = useUser();
  const teacher = user.role === "teacher";
  const [o, setO] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Overview>("/admin/overview").then(setO).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!o) return <Spinner />;

  const stats = [
    { label: "Students", value: o.students, sub: `${o.active_students} with an active plan`, href: "/admin/students" },
    { label: "Dialogues", value: o.dialogues_published, sub: `${o.dialogues_total} in total`, href: "/admin/dialogues", adminOnly: true },
    { label: "Dialogue attempts", value: o.attempts, sub: teacher ? "by your students" : "all time", href: "/admin/students" },
    { label: "Segments to review", value: o.segments_needing_review, sub: "flagged by scoring", href: "/admin/review" },
    ...(teacher ? [{ label: "Your courses", value: o.courses, sub: "shown to your students", href: "/admin/courses" }] : []),
  ].filter((s) => !(teacher && s.adminOnly));
  return (
    <>
      <PageHeader title={teacher ? "Teacher" : "Admin"} subtitle={teacher ? "Your students, their scoring review and your courses." : "Content, students and scoring review."} />
      {teacher && <JoinLink />}
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
      {!teacher && o.emails_failed > 0 && <div className="mt-6"><ErrorNote>{o.emails_failed} email(s) failed to send. Check the email provider settings.</ErrorNote></div>}
      {!teacher && <Card className="mt-8 p-6">
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
      </Card>}
    </>
  );
}

type ClassLink = { code: string; url: string; students: number };

/** A teacher's class link: students who sign up or join through it become the teacher's students. */
function JoinLink() {
  const [link, setLink] = useState<ClassLink | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { api<ClassLink>("/admin/join-link").then(setLink).catch((e) => setError(e.message)); }, []);

  const copy = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { setError("Copy failed. Select the link and copy it yourself."); }
  };
  const regenerate = async () => {
    if (!confirm("Make a new link? The current link will stop working. Students who already joined stay in your class.")) return;
    setBusy(true);
    try { setLink(await api<ClassLink>("/admin/join-link/regenerate", { method: "POST" })); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <Card className="mb-6 p-6">
      <h2 className="font-semibold">Your class link</h2>
      <p className="mt-1 text-sm text-slate-500">Share it with your students. Anyone who creates an account or joins through it
        becomes your student{link ? ` (${link.students} so far)` : ""}. You can also add students on the Students page.</p>
      {link && <div className="mt-4 flex flex-wrap gap-2">
        <input readOnly value={link.url} onFocus={(e) => e.target.select()} aria-label="Class link"
          className={`${inputClass} mt-0 min-w-0 flex-1 font-mono text-xs`} />
        <Button variant="secondary" onClick={copy}><Copy className="size-4" /> {copied ? "Copied" : "Copy"}</Button>
        <Button variant="ghost" onClick={regenerate} loading={busy}><RefreshCw className="size-4" /> New link</Button>
      </div>}
      {error && <div className="mt-3"><ErrorNote>{error}</ErrorNote></div>}
    </Card>
  );
}
