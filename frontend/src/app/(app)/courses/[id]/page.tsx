"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import CourseOutline, { type CourseOutlineData } from "@/components/CourseOutline";
import { Card, ErrorNote, LinkButton, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { courseAction, formatDuration } from "@/lib/student";

type Overview = CourseOutlineData & { image_url: string | null; at_a_glance_html: string };

/** Course Overview: reached from See Overview. Start / Resume goes to the course content (the lesson pages). */
export default function CourseOverview() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Overview>(`/courses/${id}`).then(setC).catch((e) => setError(e.message)); }, [id]);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!c) return <Spinner />;
  const completed = c.lessons.filter((l) => l.completed).length;
  const next = c.lessons.find((l) => !l.completed) ?? c.lessons[0];
  const action = courseAction({ id: c.id, lessons: c.lessons.length, completed, next_lesson: next ? { id: next.id, locked: next.locked } : null });
  const percent = c.lessons.length ? Math.round((100 * completed) / c.lessons.length) : 0;
  return (
    <>
      <Link href="/courses" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-600 hover:underline"><ArrowLeft className="size-4" /> Back to Courses</Link>
      <div className="relative flex min-h-64 flex-col gap-3 overflow-hidden rounded-2xl bg-gradient-to-r from-brand-800 to-brand-500 p-8 text-white sm:p-10">
        {/* eslint-disable-next-line @next/next/no-img-element -- served by the API with its own access checks */}
        {c.image_url && <img src={c.image_url} alt="" className="absolute inset-0 h-full w-full object-cover opacity-25" />}
        <div className="relative flex flex-1 flex-col gap-3">
          <div className="text-xs font-bold tracking-widest">COURSE OVERVIEW</div>
          <h1 className="max-w-3xl text-3xl font-bold sm:text-4xl">{c.title}</h1>
          {c.description && <p className="max-w-3xl text-base opacity-90">{c.description}</p>}
          <div className="mt-auto flex flex-wrap items-center gap-5 pt-3">
            <span className="text-sm">{percent}% completed{c.duration_minutes ? ` · ${formatDuration(c.duration_minutes)}` : ""}</span>
            {action && <LinkButton href={action.href} variant="secondary">{action.label}</LinkButton>}
          </div>
        </div>
      </div>
      {c.at_a_glance_html && (
        <Card className="mt-6 p-6">
          <h2 className="text-lg font-semibold">Course at a Glance</h2>
          {/* at_a_glance_html is sanitised by the server (allow-list) when it is saved */}
          <div className="lesson-html glance-html mt-2 text-slate-700" dangerouslySetInnerHTML={{ __html: c.at_a_glance_html }} />
        </Card>
      )}
      <Card className="mt-6 overflow-hidden">
        <div className="p-6 pb-3">
          <h2 className="text-lg font-semibold">Here&apos;s What You&apos;ll Learn</h2>
          <p className="text-sm text-slate-500">Select a chapter to explore its lessons.</p>
        </div>
        <CourseOutline course={c} firstOpenOnly />
      </Card>
    </>
  );
}
