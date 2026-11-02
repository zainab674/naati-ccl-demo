"use client";

import { Lock } from "lucide-react";
import { useEffect, useState } from "react";

import CoverImage from "@/components/CoverImage";
import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Card, ErrorNote, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { courseAction, courseState, type CourseRow } from "@/lib/student";

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
      <PageHeader title="Courses" subtitle="Continue your learning or explore courses to prepare for the NAATI CCL test."
        actions={<LanguagePicker value={language} onChange={setLanguage} />} />
      {rows.length === 0 ? <Card className="p-6 text-sm text-slate-500">No courses are available yet.</Card> : (
        <div className="grid gap-6 xl:grid-cols-2">
          {rows.map((c) => {
            const action = courseAction(c);
            const percent = c.lessons ? Math.round((100 * c.completed) / c.lessons) : 0;
            return (
              <Card key={c.id} className="grid overflow-hidden sm:grid-cols-[34%_1fr]">
                <div className="h-44 sm:h-auto sm:min-h-72"><CoverImage src={c.image_url} title={c.title} seed={c.id} /></div>
                <div className="flex min-w-0 flex-col gap-2.5 p-5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold uppercase tracking-wide text-brand-600">{c.teacher ? `From ${c.teacher}` : courseState(c)}</span>
                    {c.locked ? <Lock className="size-4 text-slate-400" /> : c.lessons > 0 && c.free_lessons === c.lessons ? <Badge tone="brand">Free</Badge> : null}
                  </div>
                  <h2 className="text-lg font-semibold">{c.title}</h2>
                  {c.description && <p className="line-clamp-3 text-sm text-slate-600">{c.description}</p>}
                  <div className="text-xs text-slate-500">{c.lessons} lesson{c.lessons === 1 ? "" : "s"}
                    {c.free_lessons > 0 && c.free_lessons < c.lessons ? ` · ${c.free_lessons} free` : ""}</div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-brand-500" style={{ width: `${percent}%` }} /></div>
                  <div className="text-xs text-slate-500">{percent}% completed</div>
                  {/* See Overview and Start/Resume sit side by side, level across the cards. */}
                  <div className="mt-auto grid grid-cols-2 gap-2.5 pt-2">
                    <LinkButton href={`/courses/${c.id}`} variant="secondary">See Overview</LinkButton>
                    {action ? <LinkButton href={action.href}>{action.label}</LinkButton> : <span />}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
