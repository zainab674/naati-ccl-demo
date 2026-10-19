"use client";

import { CheckCircle2, ChevronLeft, ChevronRight, Lock } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card, ErrorNote, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Lesson = {
  id: string; course_id: string; course_title: string; lesson_number: number; title: string; video_url: string;
  html_content: string; completed: boolean; next: { id: string; title: string; locked: boolean } | null;
  previous: { id: string; title: string } | null;
};

function Video({ url }: { url: string }) {
  if (/\.(mp4|webm)(\?|$)/i.test(url)) {
    return <video src={url} controls className="aspect-video w-full rounded-xl bg-black" />;
  }
  return (
    <iframe src={url} title="Lesson video" className="aspect-video w-full rounded-xl bg-black" allowFullScreen
      allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
      sandbox="allow-scripts allow-same-origin allow-presentation allow-popups" referrerPolicy="strict-origin-when-cross-origin" />
  );
}

export default function LessonPage() {
  const { id, lessonId } = useParams<{ id: string; lessonId: string }>();
  const [l, setL] = useState<Lesson | null>(null);
  const [error, setError] = useState<{ msg: string; locked?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Lesson>(`/lessons/${lessonId}`).then(setL)
      .catch((e) => setError({ msg: e.message, locked: e instanceof ApiError && e.status === 402 }));
  }, [lessonId]);

  const toggle = async () => {
    if (!l) return;
    setBusy(true);
    const r = await api<{ completed: boolean }>(`/lessons/${l.id}/complete`, { method: l.completed ? "DELETE" : "POST" });
    setL({ ...l, completed: r.completed });
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
  return (
    <div className="mx-auto max-w-3xl">
      <Link href={`/courses/${id}`} className="text-sm text-brand-600 hover:underline">{l.course_title}</Link>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight">{l.lesson_number}. {l.title}</h1>
      {l.video_url && <div className="mt-6"><Video url={l.video_url} /></div>}
      {/* html_content is sanitised by the server (allow-list) when it is saved */}
      {l.html_content && <Card className="lesson-html mt-6 p-6" ><div dangerouslySetInnerHTML={{ __html: l.html_content }} /></Card>}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <Button variant={l.completed ? "secondary" : "primary"} onClick={toggle} loading={busy}>
          <CheckCircle2 className="size-4" /> {l.completed ? "Completed" : "Mark as complete"}
        </Button>
        <div className="flex gap-2">
          {l.previous && <Link href={`/courses/${id}/lessons/${l.previous.id}`} className="inline-flex h-10 items-center gap-1 rounded-lg px-3 text-sm text-slate-600 hover:bg-slate-100"><ChevronLeft className="size-4" /> Previous</Link>}
          {l.next && (l.next.locked
            ? <Link href="/pricing" className="inline-flex h-10 items-center gap-1 rounded-lg px-3 text-sm text-slate-600 hover:bg-slate-100"><Lock className="size-4" /> Next lesson</Link>
            : <Link href={`/courses/${id}/lessons/${l.next.id}`} className="inline-flex h-10 items-center gap-1 rounded-lg bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700">Next lesson <ChevronRight className="size-4" /></Link>)}
        </div>
      </div>
    </div>
  );
}
