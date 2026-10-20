"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Card, cx, ErrorNote, Field, inputClass, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api, fetchLanguages, type Language } from "@/lib/api";

type Lesson = { id: string; lesson_number: number; title: string; video_url: string; html_content: string; is_free: boolean; status: string };
type Course = { id: string; key: string; title: string; description: string; status: string; is_free: boolean; sort_order: number; language: string | null; lessons: Lesson[] };

export default function CourseEditor() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<Course | null>(null);
  const [form, setForm] = useState({ title: "", description: "", sort_order: 0, language: "" });
  const [languages, setLanguages] = useState<Language[]>([]);
  useEffect(() => { fetchLanguages().then(setLanguages).catch(() => {}); }, []);
  const [selected, setSelected] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  const apply = useCallback((x: Course) => {
    setC(x);
    setForm({ title: x.title, description: x.description, sort_order: x.sort_order, language: x.language ?? "" });
  }, []);
  const load = useCallback(() => api<Course>(`/admin/courses/${id}`).then(apply), [id, apply]);
  useEffect(() => {
    api<Course>(`/admin/courses/${id}`).then(apply).catch((e) => setMsg({ err: e.message }));
  }, [id, apply]);

  const patchCourse = async (patch: object) => {
    setMsg({});
    try { setC(await api<Course>(`/admin/courses/${id}`, { method: "PATCH", json: patch })); setMsg({ ok: "Saved." }); }
    catch (e) { setMsg({ err: (e as Error).message }); }
  };

  const addLesson = async () => {
    try {
      const l = await api<Lesson>(`/admin/courses/${id}/lessons`, { method: "POST", json: { status: "Draft" } });
      await load();
      setSelected(l.id);
    } catch (e) { setMsg({ err: (e as Error).message }); }
  };

  if (!c) return msg.err ? <ErrorNote>{msg.err}</ErrorNote> : <Spinner />;
  const lesson = c.lessons.find((l) => l.id === selected);
  return (
    <>
      <PageHeader title={c.title} subtitle={<><span className="font-mono">{c.key}</span> · <Link href="/admin/courses" className="text-brand-600 hover:underline">All courses</Link></>}
        actions={<div className="flex items-center gap-2"><Badge tone={statusTone(c.status)}>{c.status}</Badge>
          {c.status !== "Published" ? <Button size="sm" onClick={() => patchCourse({ status: "Published" })}>Publish</Button>
            : <Button size="sm" variant="secondary" onClick={() => patchCourse({ status: "Archived" })}>Hide</Button>}</div>} />
      {msg.ok && <div className="mb-4"><SuccessNote>{msg.ok}</SuccessNote></div>}
      {msg.err && <div className="mb-4"><ErrorNote>{msg.err}</ErrorNote></div>}
      <Card className="mb-6 grid gap-4 p-6 sm:grid-cols-[2fr_1fr]">
        <Field label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <Field label="Sort order" type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
        <label className="block sm:col-span-2"><span className="text-sm font-medium text-slate-700">Language</span>
          <select className={inputClass} value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
            <option value="">All languages (e.g. the introduction course)</option>
            {languages.map((l) => <option key={l.code} value={l.code}>{l.name} only</option>)}
          </select></label>
        <label className="block sm:col-span-2"><span className="text-sm font-medium text-slate-700">Description</span>
          <textarea className={cx(inputClass, "h-20 py-2")} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        <div className="sm:col-span-2 flex justify-end"><Button onClick={() => patchCourse({ ...form, language: form.language || null })}>Save course</Button></div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <Card className="h-fit">
          <ul className="divide-y divide-slate-100">
            {c.lessons.map((l) => (
              <li key={l.id}>
                <button onClick={() => setSelected(l.id)} className={cx("flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm hover:bg-slate-50", selected === l.id && "bg-brand-50")}>
                  <span><span className="mr-2 tabular-nums text-slate-400">{l.lesson_number}</span>{l.title}</span>
                  <span className="space-x-1">{l.is_free && <Badge tone="brand">Free</Badge>}{l.status !== "Published" && <Badge tone={statusTone(l.status)}>{l.status}</Badge>}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="p-3"><Button size="sm" variant="ghost" onClick={addLesson}><Plus className="size-4" /> Add lesson</Button></div>
        </Card>
        {lesson ? <LessonEditor key={lesson.id} lesson={lesson} onSaved={() => load()} /> : <Card className="p-6 text-sm text-slate-500">Select a lesson to edit it.</Card>}
      </div>
    </>
  );
}

function LessonEditor({ lesson, onSaved }: { lesson: Lesson; onSaved: () => void }) {
  const [f, setF] = useState(lesson);
  const [preview, setPreview] = useState(lesson.html_content);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState(false);

  // Preview shows exactly what the server will store after sanitising.
  useEffect(() => {
    const t = setTimeout(() => {
      api<{ html: string }>("/admin/sanitize-html", { method: "POST", json: { html: f.html_content } }).then((r) => setPreview(r.html)).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [f.html_content]);

  const save = async () => {
    setBusy(true);
    setMsg({});
    try {
      const { id, ...body } = f;
      await api(`/admin/lessons/${id}`, { method: "PATCH", json: body });
      setMsg({ ok: "Lesson saved." });
      onSaved();
    } catch (e) { setMsg({ err: (e as Error).message }); }
    setBusy(false);
  };

  return (
    <Card className="space-y-4 p-6">
      <div className="grid gap-4 sm:grid-cols-[6rem_1fr]">
        <Field label="Number" type="number" min={1} value={f.lesson_number} onChange={(e) => setF({ ...f, lesson_number: Number(e.target.value) })} />
        <Field label="Title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
      </div>
      <Field label="Video URL (embed link)" value={f.video_url} onChange={(e) => setF({ ...f, video_url: e.target.value })} placeholder="https://www.youtube.com/embed/..." />
      <div className="grid gap-4 lg:grid-cols-2">
        <label className="block"><span className="text-sm font-medium text-slate-700">Lesson text (HTML)</span>
          <textarea className={cx(inputClass, "h-72 py-2 font-mono text-xs")} value={f.html_content} onChange={(e) => setF({ ...f, html_content: e.target.value })} /></label>
        <div><span className="text-sm font-medium text-slate-700">Preview (sanitised)</span>
          <div className="lesson-html mt-1 h-72 overflow-auto rounded-lg border border-slate-200 p-3 text-sm" dangerouslySetInnerHTML={{ __html: preview }} /></div>
      </div>
      <div className="flex flex-wrap items-center gap-6 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={f.is_free} onChange={(e) => setF({ ...f, is_free: e.target.checked })} className="accent-brand-600" /> Free lesson</label>
        <label className="flex items-center gap-2">Status
          <select className={cx(inputClass, "mt-0 w-36")} value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
            <option>Draft</option><option>Published</option><option>Archived</option>
          </select></label>
      </div>
      {msg.ok && <SuccessNote>{msg.ok}</SuccessNote>}
      {msg.err && <ErrorNote>{msg.err}</ErrorNote>}
      <div className="flex justify-end"><Button onClick={save} loading={busy}>Save lesson</Button></div>
    </Card>
  );
}
