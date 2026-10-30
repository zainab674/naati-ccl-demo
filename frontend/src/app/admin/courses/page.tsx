"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Badge, Button, Card, ErrorNote, Field, Modal, PageHeader, Spinner } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api } from "@/lib/api";

type CourseRow = { id: string; key: string; title: string; status: string; is_free: boolean; lesson_count: number;
  owner: { id: string; name: string } | null };

const slug = (title: string) => title.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 100);

export default function AdminCourses() {
  const router = useRouter();
  const { user } = useUser();
  const isAdmin = user.role === "admin";
  const [keyEdited, setKeyEdited] = useState(false);
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
      <PageHeader title={isAdmin ? "Courses" : "My courses"}
        subtitle={isAdmin ? "Courses and lessons. Lessons can be free or paid. Teachers' courses are shown only to their own students."
          : "Courses you create are shown only to your own students, alongside Benchmark's courses."}
        actions={<Button onClick={() => setCreating(true)}>New course</Button>} />
      {error && !creating && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {rows.map((c) => (
              <li key={c.id}>
                <Link href={`/admin/courses/${c.id}`} className="flex items-center justify-between px-5 py-3 hover:bg-slate-50">
                  <div><div className="font-medium">{c.title}</div>
                    <div className="font-mono text-xs text-slate-400">{c.key} · {c.lesson_count} lessons</div>
                    {isAdmin && <div className="text-xs text-slate-500">{c.owner ? `By ${c.owner.name}, for their students` : "Benchmark, for every student"}</div>}</div>
                  <div className="space-x-1"><Badge tone={statusTone(c.status)}>{c.status}</Badge>{c.is_free && <Badge tone="brand">Free</Badge>}</div>
                </Link>
              </li>
            ))}
            {rows.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">{isAdmin ? "No courses yet. Create one or import a CSV." : "No courses yet. Create one for your students."}</li>}
          </ul>
        </Card>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title="New course">
        <div className="space-y-4">
          <Field label="Title" value={form.title}
            onChange={(e) => setForm({ title: e.target.value, key: keyEdited ? form.key : slug(e.target.value) })} />
          <Field label="Key" value={form.key} onChange={(e) => { setKeyEdited(true); setForm({ ...form, key: e.target.value.toLowerCase() }); }}
            hint="A short unique name, filled in from the title. Used by CSV import, e.g. intro-to-ccl" />
          {error && <ErrorNote>{error}</ErrorNote>}
          <div className="flex justify-end"><Button onClick={create}>Create</Button></div>
        </div>
      </Modal>
    </>
  );
}
