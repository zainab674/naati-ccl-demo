"use client";

import { CheckCircle2, Circle, Lock, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Card, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

type Course = { id: string; title: string; description: string;
  lessons: { id: string; lesson_number: number; title: string; is_free: boolean; locked: boolean; completed: boolean; has_video: boolean }[] };

export default function CoursePage() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<Course | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Course>(`/courses/${id}`).then(setC).catch((e) => setError(e.message)); }, [id]);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!c) return <Spinner />;
  return (
    <>
      <PageHeader title={c.title} subtitle={<Link href="/courses" className="text-brand-600 hover:underline">All courses</Link>} />
      {c.description && <p className="-mt-2 mb-6 max-w-3xl text-slate-600">{c.description}</p>}
      <Card className="max-w-3xl overflow-hidden">
        <ol className="divide-y divide-slate-100">
          {c.lessons.map((l) => {
            const inner = (
              <div className="flex items-center gap-3 px-5 py-4">
                {l.completed ? <CheckCircle2 className="size-5 text-emerald-600" /> : l.locked ? <Lock className="size-5 text-slate-300" /> : <Circle className="size-5 text-slate-300" />}
                <span className="w-6 text-sm tabular-nums text-slate-400">{l.lesson_number}</span>
                <span className="flex-1 font-medium">{l.title}</span>
                {l.has_video && <PlayCircle className="size-4 text-slate-400" />}
                {l.is_free && <Badge tone="brand">Free</Badge>}
              </div>
            );
            return <li key={l.id}>{l.locked ? <Link href="/pricing" className="block opacity-70 hover:bg-slate-50" title="Choose a plan to unlock">{inner}</Link>
              : <Link href={`/courses/${c.id}/lessons/${l.id}`} className="block hover:bg-slate-50">{inner}</Link>}</li>;
          })}
          {c.lessons.length === 0 && <li className="px-5 py-6 text-sm text-slate-500">No lessons yet.</li>}
        </ol>
      </Card>
    </>
  );
}
