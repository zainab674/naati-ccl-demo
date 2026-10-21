"use client";

import { PlayCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import CourseOutline, { type CourseOutlineData, lessonHref } from "@/components/CourseOutline";
import { Card, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

export default function CoursePage() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<CourseOutlineData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<CourseOutlineData>(`/courses/${id}`).then(setC).catch((e) => setError(e.message)); }, [id]);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!c) return <Spinner />;
  const done = c.lessons.filter((l) => l.completed).length;
  const resume = c.lessons.find((l) => !l.completed && !l.locked);
  return (
    <>
      <PageHeader title={c.title} subtitle={<Link href="/courses" className="text-brand-600 hover:underline">All courses</Link>}
        actions={resume && (
          <Link href={lessonHref(c.id, resume)} className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700">
            <PlayCircle className="size-4" /> {done ? "Continue" : "Start"}: Lesson {resume.number}
          </Link>
        )} />
      {c.description && <p className="-mt-2 mb-6 max-w-3xl text-slate-600">{c.description}</p>}
      <div className="mb-4 max-w-3xl">
        <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-brand-500" style={{ width: c.lessons.length ? `${(100 * done) / c.lessons.length}%` : "0%" }} /></div>
        <div className="mt-1 text-xs text-slate-500">{done} of {c.lessons.length} lessons completed</div>
      </div>
      <Card className="max-w-3xl overflow-hidden"><CourseOutline course={c} /></Card>
    </>
  );
}
