"use client";

import { ArrowDown, ArrowUp, FileText, FolderPlus, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import HtmlEditor from "@/components/HtmlEditor";
import ImageField from "@/components/ImageField";
import { Badge, Button, Card, cx, ErrorNote, Field, inputClass, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api, fetchLanguages, type Language } from "@/lib/api";
import { fileSize } from "@/lib/resources";

type Lesson = { id: string; lesson_number: number; title: string; video_url: string; html_content: string; notes_html: string; duration_minutes: number | null; is_free: boolean; status: string;
  chapter_id: string | null; number: string | null; pdf: { name: string; size: number; url: string } | null };
type Chapter = { id: string; number: number; title: string };
type Course = { id: string; image_url: string | null; key: string; title: string; description: string; at_a_glance_html: string; status: string; is_free: boolean; sort_order: number; language: string | null; chapters: Chapter[]; lessons: Lesson[] };

// The six boxes from the client's Round 1 mockup, as a starting point for staff to edit per course.
const GLANCE_STARTER = `<ul>
  <li><strong>Self-paced</strong> Learn on your schedule</li>
  <li><strong>Structured lessons</strong> Step-by-step instruction</li>
  <li><strong>Practical activities</strong> Apply interpreting techniques</li>
  <li><strong>Exam focused</strong> Targeted preparation</li>
  <li><strong>Track progress</strong> Pick up where you left off</li>
  <li><strong>Skill development</strong> Build confidence</li>
</ul>
`;

export default function CourseEditor() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<Course | null>(null);
  const [form, setForm] = useState({ title: "", description: "", at_a_glance_html: "", sort_order: 0, language: "" });
  const [languages, setLanguages] = useState<Language[]>([]);
  useEffect(() => { fetchLanguages().then(setLanguages).catch(() => {}); }, []);
  const [selected, setSelected] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});

  const apply = useCallback((x: Course) => {
    setC(x);
    setForm({ title: x.title, description: x.description, at_a_glance_html: x.at_a_glance_html, sort_order: x.sort_order, language: x.language ?? "" });
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

  const addLesson = async (chapterId: string | null = null) => {
    try {
      const l = await api<Lesson>(`/admin/courses/${id}/lessons`, { method: "POST", json: { status: "Draft", chapter_id: chapterId } });
      await load();
      setSelected(l.id);
    } catch (e) { setMsg({ err: (e as Error).message }); }
  };

  const chapterAction = async (path: string, init: Parameters<typeof api>[1]) => {
    setMsg({});
    try { setC(await api<Course>(path, init)); } catch (e) { setMsg({ err: (e as Error).message }); }
  };
  const addChapter = () => {
    const title = prompt("Chapter title", `Chapter ${(c?.chapters.length ?? 0) + 1}`);
    if (title?.trim()) chapterAction(`/admin/courses/${id}/chapters`, { method: "POST", json: { title: title.trim() } });
  };
  const renameChapter = (ch: Chapter) => {
    const title = prompt("Chapter title", ch.title);
    if (title?.trim() && title.trim() !== ch.title) chapterAction(`/admin/chapters/${ch.id}`, { method: "PATCH", json: { title: title.trim() } });
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
        <div className="sm:col-span-2">
          <HtmlEditor label="Course at a Glance (shown on the course overview page, hidden when empty)" value={form.at_a_glance_html} heightClass="h-72" previewClass="glance-html"
            onChange={(at_a_glance_html) => setForm((x) => ({ ...x, at_a_glance_html }))} />
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Button size="sm" variant="secondary" onClick={() => { if (!form.at_a_glance_html.trim() || confirm("Replace the current Course at a Glance text with the six-box starter?")) setForm((x) => ({ ...x, at_a_glance_html: GLANCE_STARTER })); }}>Use six-box starter</Button>
            <p className="text-xs text-slate-500">Each item of a bulleted list becomes a box: the bold part is its title. Icons go by position. Edit the wording so it is true for this course.</p>
          </div>
        </div>
        <div className="sm:col-span-2"><ImageField<Course> label="Course image" url={c.image_url} apiPath={`/admin/courses/${id}/image`}
          hint="Shown on the course card and overview page. PNG, JPEG or WebP, up to 4 MB." onSaved={apply} /></div>
        <div className="sm:col-span-2 flex justify-end"><Button onClick={() => patchCourse({ ...form, language: form.language || null })}>Save course</Button></div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <Card className="h-fit overflow-hidden">
          {[...c.chapters.map((ch) => ({ ch, lessons: c.lessons.filter((l) => l.chapter_id === ch.id) })),
            { ch: null as Chapter | null, lessons: c.lessons.filter((l) => !l.chapter_id || !c.chapters.some((ch) => ch.id === l.chapter_id)) }]
            .filter((g) => g.ch || g.lessons.length || !c.chapters.length)
            .map(({ ch, lessons }, gi, groups) => (
              <div key={ch?.id ?? "loose"} className="border-b border-slate-100 last:border-0">
                {(ch || c.chapters.length > 0) && (
                  <div className="flex items-center gap-1 bg-slate-50 px-3 py-2">
                    <span className="flex-1 truncate text-xs font-semibold uppercase tracking-wide text-slate-600">{ch ? `Chapter ${ch.number}: ${ch.title}` : "Not in a chapter"}</span>
                    {ch && <>
                      <button title="Rename" onClick={() => renameChapter(ch)} className="rounded p-1 text-slate-400 hover:bg-white hover:text-ink"><Pencil className="size-3.5" /></button>
                      <button title="Move up" disabled={gi === 0} onClick={() => chapterAction(`/admin/chapters/${ch.id}`, { method: "PATCH", json: { move: "up" } })} className="rounded p-1 text-slate-400 hover:bg-white hover:text-ink disabled:opacity-30"><ArrowUp className="size-3.5" /></button>
                      <button title="Move down" disabled={!groups[gi + 1]?.ch} onClick={() => chapterAction(`/admin/chapters/${ch.id}`, { method: "PATCH", json: { move: "down" } })} className="rounded p-1 text-slate-400 hover:bg-white hover:text-ink disabled:opacity-30"><ArrowDown className="size-3.5" /></button>
                      <button title="Delete chapter (its lessons are kept)" onClick={() => { if (confirm(`Delete chapter "${ch.title}"? Its lessons are kept and move to "Not in a chapter".`)) chapterAction(`/admin/chapters/${ch.id}`, { method: "DELETE" }); }} className="rounded p-1 text-slate-400 hover:bg-white hover:text-rose-600"><Trash2 className="size-3.5" /></button>
                    </>}
                  </div>
                )}
                <ul className="divide-y divide-slate-100">
                  {lessons.map((l) => (
                    <li key={l.id}>
                      <button onClick={() => setSelected(l.id)} className={cx("flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm hover:bg-slate-50", selected === l.id && "bg-brand-50")}>
                        <span><span className="mr-2 tabular-nums text-slate-400">{l.number ?? l.lesson_number}</span>{l.title}</span>
                        <span className="space-x-1">{l.is_free && <Badge tone="brand">Free</Badge>}{l.status !== "Published" && <Badge tone={statusTone(l.status)}>{l.status}</Badge>}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="px-2 py-1.5"><Button size="sm" variant="ghost" onClick={() => addLesson(ch?.id ?? null)}><Plus className="size-4" /> Add lesson</Button></div>
              </div>
            ))}
          <div className="border-t border-slate-100 p-2"><Button size="sm" variant="secondary" onClick={addChapter}><FolderPlus className="size-4" /> Add chapter</Button></div>
        </Card>
        {lesson ? <LessonEditor key={lesson.id} lesson={lesson} chapters={c.chapters} onSaved={() => load()} /> : <Card className="p-6 text-sm text-slate-500">Select a lesson to edit it.</Card>}
      </div>
    </>
  );
}

/** The lesson's PDF handout: saved as soon as it is chosen (separately from the lesson's Save button). */
function LessonPdf({ lesson, onSaved }: { lesson: Lesson; onSaved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    try { await api(`/admin/lessons/${lesson.id}/pdf`, { method: "POST", body: fd }); onSaved(); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  const remove = async () => {
    if (!confirm("Remove this lesson's PDF?")) return;
    setBusy(true);
    try { await api(`/admin/lessons/${lesson.id}/pdf`, { method: "DELETE" }); onSaved(); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  return (
    <div className="rounded-lg border border-slate-200 p-4 text-sm">
      <div className="font-medium text-slate-700">PDF handout (optional)</div>
      {lesson.pdf ? (
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <a href={lesson.pdf.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-brand-600 hover:underline">
            <FileText className="size-4" /> {lesson.pdf.name}</a>
          <span className="text-slate-500">{fileSize(lesson.pdf.size)}</span>
          <label className="cursor-pointer text-brand-600 hover:underline">Replace
            <input type="file" accept="application/pdf,.pdf" className="sr-only" disabled={busy} onChange={(e) => upload(e.target.files?.[0])} /></label>
          <Button size="sm" variant="ghost" onClick={remove} loading={busy}>Remove</Button>
        </div>
      ) : (
        <input type="file" accept="application/pdf,.pdf" disabled={busy} onChange={(e) => upload(e.target.files?.[0])}
          className="mt-2 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200" />
      )}
      <p className="mt-2 text-xs text-slate-500">Shown under the lesson text, with the same access as the lesson. Or add a <code>pdf_url</code> column to courses.csv.</p>
      {error && <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>}
    </div>
  );
}

function LessonEditor({ lesson, chapters, onSaved }: { lesson: Lesson; chapters: Chapter[]; onSaved: () => void }) {
  const [f, setF] = useState(lesson);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    setMsg({});
    try {
      const { id, number: _display, pdf: _pdf, ...body } = f;  // eslint-disable-line @typescript-eslint/no-unused-vars
      await api(`/admin/lessons/${id}`, { method: "PATCH", json: body });
      setMsg({ ok: "Lesson saved." });
      onSaved();
    } catch (e) { setMsg({ err: (e as Error).message }); }
    setBusy(false);
  };

  return (
    <Card className="space-y-4 p-6">
      <div className="grid gap-4 sm:grid-cols-[6rem_1fr]">
        <Field label="Order" type="number" min={1} value={f.lesson_number} onChange={(e) => setF({ ...f, lesson_number: Number(e.target.value) })} />
        <Field label="Title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
      </div>
      <label className="block"><span className="text-sm font-medium text-slate-700">Chapter</span>
        <select className={inputClass} value={f.chapter_id ?? ""} onChange={(e) => setF({ ...f, chapter_id: e.target.value || null })}>
          <option value="">Not in a chapter</option>
          {chapters.map((ch) => <option key={ch.id} value={ch.id}>Chapter {ch.number}: {ch.title}</option>)}
        </select></label>
      <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
        <Field label="YouTube link or video URL" value={f.video_url} onChange={(e) => setF({ ...f, video_url: e.target.value })} placeholder="https://www.youtube.com/watch?v=..." />
        <Field label="Length (minutes)" type="number" min={1} max={6000} value={f.duration_minutes ?? ""}
          onChange={(e) => setF({ ...f, duration_minutes: e.target.value ? Number(e.target.value) : null })} />
      </div>
      <HtmlEditor label="Lesson text (HTML)" value={f.html_content} onChange={(html_content) => setF((x) => ({ ...x, html_content }))} heightClass="h-72" />
      <HtmlEditor label="Notes (shown to students under the lesson text)" value={f.notes_html} onChange={(notes_html) => setF((x) => ({ ...x, notes_html }))} />
      <LessonPdf lesson={lesson} onSaved={onSaved} />
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
