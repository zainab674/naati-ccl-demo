"use client";

import { GraduationCap, Lock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Card, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

type CourseRow = { id: string; title: string; description: string; lessons: number; completed: number; free_lessons: number; locked: boolean };

export default function CoursesPage() {
  const [rows, setRows] = useState<CourseRow[] | null>(null);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState("");
  useEffect(() => {
    let stale = false;
    api<CourseRow[]>(`/courses?language=${language}`).then((d) => { if (!stale) setRows(d); }).catch((e) => setError(e.message));
    return () => { stale = true; };
  }, [language]);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!rows) return <Spinner />;
  return (
    <>
      <PageHeader title="Courses" subtitle="Video lessons and notes to prepare for the CCL test." actions={<LanguagePicker value={language} onChange={setLanguage} />} />
      {rows.length === 0 ? <Card className="p-6 text-sm text-slate-500">No courses are available yet.</Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {rows.map((c) => (
            <Link key={c.id} href={`/courses/${c.id}`}>
              <Card className="h-full p-6 transition-shadow hover:shadow-md">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="flex items-center gap-2 text-lg font-semibold"><GraduationCap className="size-5 text-brand-600" />{c.title}</h2>
                  {c.locked ? <Lock className="size-4 text-slate-400" /> : c.free_lessons === c.lessons ? <Badge tone="brand">Free</Badge> : null}
                </div>
                {c.description && <p className="mt-2 text-sm text-slate-600">{c.description}</p>}
                <div className="mt-5">
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full bg-brand-500" style={{ width: c.lessons ? `${(100 * c.completed) / c.lessons}%` : "0%" }} />
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{c.completed} of {c.lessons} lessons completed{c.free_lessons > 0 && c.free_lessons < c.lessons ? ` · ${c.free_lessons} free` : ""}</div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
