"use client";

import { ArrowLeft, ArrowRight, CheckCircle2, ChevronLeft, ListTree, Lock, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import CourseOutline, { type CourseOutlineData } from "@/components/CourseOutline";
import { Button, Card, cx, ErrorNote, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Lesson = {
  id: string; course_id: string; course_title: string; lesson_number: number; number: string; title: string;
  chapter: { number: number; title: string } | null; video_url: string; html_content: string; completed: boolean;
  next: { id: string; title: string; locked: boolean } | null; previous: { id: string; title: string } | null;
};

const SIDEBAR_KEY = "course-sidebar-closed";

function Video({ url }: { url: string }) {
  if (/\.(mp4|webm)(\?|$)/i.test(url)) {
    return <video src={url} controls className="aspect-video w-full bg-black" />;
  }
  return (
    <iframe src={url} title="Lesson video" className="aspect-video w-full bg-black" allowFullScreen
      allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
      sandbox="allow-scripts allow-same-origin allow-presentation allow-popups" referrerPolicy="strict-origin-when-cross-origin" />
  );
}

export default function LessonPage() {
  const { id, lessonId } = useParams<{ id: string; lessonId: string }>();
  const [l, setL] = useState<Lesson | null>(null);
  const [course, setCourse] = useState<CourseOutlineData | null>(null);
  const [error, setError] = useState<{ msg: string; locked?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [closed, setClosed] = useState(() => {
    try { return typeof window !== "undefined" && localStorage.getItem(SIDEBAR_KEY) === "1"; } catch { return false; }
  });
  const [mobileOutline, setMobileOutline] = useState(false);

  useEffect(() => {
    api<Lesson>(`/lessons/${lessonId}`).then(setL)
      .catch((e) => setError({ msg: e.message, locked: e instanceof ApiError && e.status === 402 }));
  }, [lessonId]);
  useEffect(() => { api<CourseOutlineData>(`/courses/${id}`).then(setCourse).catch(() => {}); }, [id]);

  const setSidebar = (isClosed: boolean) => {
    setClosed(isClosed);
    try { localStorage.setItem(SIDEBAR_KEY, isClosed ? "1" : "0"); } catch { /* storage unavailable */ }
  };

  const toggleComplete = async () => {
    if (!l) return;
    setBusy(true);
    const r = await api<{ completed: boolean }>(`/lessons/${l.id}/complete`, { method: l.completed ? "DELETE" : "POST" });
    setL({ ...l, completed: r.completed });
    // Keep the sidebar ticks in step.
    setCourse((c) => c && {
      ...c,
      lessons: c.lessons.map((x) => (x.id === l.id ? { ...x, completed: r.completed } : x)),
      chapters: c.chapters.map((g) => ({ ...g, lessons: g.lessons.map((x) => (x.id === l.id ? { ...x, completed: r.completed } : x)) })),
    });
    setBusy(false);
  };

  if (error) {
    return error.locked ? (
      <Card className="mx-auto max-w-lg p-8 text-center">
        <Lock className="mx-auto size-8 text-slate-400" />
        <h1 className="mt-3 text-lg font-semibold">This lesson is part of a paid plan</h1>
        <Link href="/pricing" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">See plans</Link>
      </Card>
    ) : <ErrorNote>{error.msg}</ErrorNote>;
  }
  if (!l) return <Spinner />;

  const outline = course && (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="min-w-0"><div className="text-sm font-semibold">Course Content</div>
          <Link href={`/courses/${id}`} className="block truncate text-xs text-slate-500 hover:text-brand-600">{l.course_title}</Link></div>
        <button onClick={() => setSidebar(true)} aria-label="Hide course content" className="hidden rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-ink lg:block">
          <ChevronLeft className="size-4" /></button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto p-2"><CourseOutline course={course} currentId={l.id} compact /></div>
    </Card>
  );

  return (
    <div className={cx("grid gap-6", closed ? "lg:grid-cols-[2.5rem_1fr]" : "lg:grid-cols-[18rem_1fr]")}>
      {/* Sidebar (desktop): open, or folded to a thin rail. */}
      <aside className="hidden lg:block">
        <div className="sticky top-6">
          {closed
            ? <button onClick={() => setSidebar(false)} aria-label="Show course content" title="Course content"
                className="flex size-10 items-center justify-center rounded-lg bg-white text-slate-500 ring-1 ring-slate-200 hover:text-ink"><PanelLeftOpen className="size-4" /></button>
            : outline}
        </div>
      </aside>

      <div className="min-w-0 space-y-4">
        {/* Phones: the outline opens above the lesson. */}
        <div className="lg:hidden">
          <button onClick={() => setMobileOutline(!mobileOutline)} className="inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-medium ring-1 ring-slate-200">
            <ListTree className="size-4" /> Course content</button>
          {mobileOutline && <div className="mt-3">{outline}</div>}
        </div>

        {l.video_url && <div className="overflow-hidden rounded-xl ring-1 ring-slate-200"><Video url={l.video_url} /></div>}

        <Card className="p-6">
          {l.chapter && <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Chapter {l.chapter.number}: {l.chapter.title}</div>}
          <h1 className="mt-1 text-xl font-semibold tracking-tight">Lesson {l.number}: {l.title}</h1>
          {/* html_content is sanitised by the server (allow-list) when it is saved */}
          {l.html_content && <div className="lesson-html mt-4 text-slate-700" dangerouslySetInnerHTML={{ __html: l.html_content }} />}
          <div className="mt-6 border-t border-slate-100 pt-5">
            <Button variant={l.completed ? "secondary" : "primary"} size="sm" onClick={toggleComplete} loading={busy}>
              <CheckCircle2 className="size-4" /> {l.completed ? "Completed" : "Mark as complete"}
            </Button>
          </div>
        </Card>

        <div className="flex items-center justify-between gap-3">
          {l.previous
            ? <Link href={`/courses/${id}/lessons/${l.previous.id}`} className="inline-flex h-10 items-center gap-2 rounded-lg bg-white px-4 text-sm font-medium text-ink ring-1 ring-slate-300 hover:bg-slate-50"><ArrowLeft className="size-4" /> Previous</Link>
            : <span />}
          {l.next && (l.next.locked
            ? <Link href="/pricing" className="inline-flex h-10 items-center gap-2 rounded-lg bg-white px-4 text-sm font-medium text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50"><Lock className="size-4" /> Next</Link>
            : <Link href={`/courses/${id}/lessons/${l.next.id}`} className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-600 px-5 text-sm font-medium text-white hover:bg-brand-700">Next <ArrowRight className="size-4" /></Link>)}
        </div>
      </div>
    </div>
  );
}
