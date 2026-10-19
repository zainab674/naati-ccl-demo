"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Button, Card, ErrorNote, Field, Modal, PageHeader, Spinner } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api } from "@/lib/api";

type CourseRow = { id: string; key: string; title: string; status: string; is_free: boolean; lesson_count: number };

export default function AdminCourses() {
  const router = useRouter();
  const [rows, setRows] = useState<CourseRow[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ key: "", title: "" });
  const [error, setError] = useState("");

  useEffect(() => { api<CourseRow[]>("/admin/courses").then(setRows).catch((e) => setError(e.message)); }, []);

  const create = async () => {
    setError("");
    try {
      const c = await api<CourseRow>("/admin/courses", { method: "POST", json: form });
      router.push(`/admin/courses/${c.id}`);
    } catch (e) { setError((e as Error).message); }
  };

  return (
    <>
      <PageHeader title="Courses" subtitle="Courses and lessons. Lessons can be free or paid."
        actions={<Button onClick={() => setCreating(true)}>New course</Button>} />
      {error && !creating && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {rows.map((c) => (
              <li key={c.id} className="flex items-center justify-between px-5 py-3">
                <div><Link href={`/admin/courses/${c.id}`} className="font-medium hover:underline">{c.title}</Link>
                  <div className="font-mono text-xs text-slate-400">{c.key} · {c.lesson_count} lessons</div></div>
                <div className="space-x-1"><Badge tone={statusTone(c.status)}>{c.status}</Badge>{c.is_free && <Badge tone="brand">Free</Badge>}</div>
              </li>
            ))}
            {rows.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">No courses yet. Create one or import a CSV.</li>}
          </ul>
        </Card>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title="New course">
        <div className="space-y-4">
          <Field label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <Field label="Key" value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value.toLowerCase() })} hint="Used by CSV import, e.g. intro-to-ccl" />
          {error && <ErrorNote>{error}</ErrorNote>}
          <div className="flex justify-end"><Button onClick={create}>Create</Button></div>
        </div>
      </Modal>
    </>
  );
}
