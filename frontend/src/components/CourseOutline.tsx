"use client";

/** Course outline: chapters with their lessons (numbered 1.1, 1.2, 2.1...), each lesson's done / current / locked
 * state. Used as the lesson-page sidebar ("Course Content") and on the course overview page. */
import { CheckCircle2, ChevronDown, FileText, Folder, Lock, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { cx } from "./ui";

export type OutlineLesson = {
  id: string; lesson_number: number; number: string; title: string; is_free: boolean; locked: boolean; completed: boolean; has_video: boolean;
};
export type OutlineChapter = { id: string | null; number: number | null; title: string | null; lessons: OutlineLesson[] };
export type CourseOutlineData = { id: string; title: string; description: string; chapters: OutlineChapter[]; lessons: OutlineLesson[] };

export const lessonHref = (courseId: string, l: OutlineLesson) => (l.locked ? "/pricing" : `/courses/${courseId}/lessons/${l.id}`);

export default function CourseOutline({ course, currentId, compact }: { course: CourseOutlineData; currentId?: string; compact?: boolean }) {
  const chaptered = course.chapters.some((g) => g.id);
  // Chapters start open; the reader can fold any of them.
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const toggle = (key: string) => setClosed((s) => { const n = new Set(s); if (n.has(key)) n.delete(key); else n.add(key); return n; });

  return (
    <div className={cx(!compact && "divide-y divide-slate-100")}>
      {course.chapters.map((g) => {
        const key = g.id ?? "loose";
        const open = !closed.has(key) || g.lessons.some((l) => l.id === currentId);
        const done = g.lessons.filter((l) => l.completed).length;
        const heading = g.id ? `Chapter ${g.number}: ${g.title}` : chaptered ? "More lessons" : null;
        return (
          <section key={key} className={cx(compact ? "border-b border-slate-100 py-1 last:border-0" : "py-1")}>
            {heading && (
              <button onClick={() => toggle(key)} aria-expanded={open}
                className={cx("flex w-full items-center gap-2.5 text-left hover:bg-slate-50", compact ? "rounded-lg px-3 py-2.5" : "px-5 py-3.5")}>
                <Folder className="size-4 shrink-0 text-brand-600" />
                <span className={cx("flex-1 font-semibold text-ink", compact ? "text-sm" : "")}>{heading}</span>
                {!compact && <span className="text-xs tabular-nums text-slate-400">{done}/{g.lessons.length}</span>}
                <ChevronDown className={cx("size-4 shrink-0 text-slate-400 transition-transform", !open && "-rotate-90")} />
              </button>
            )}
            {open && (
              <ol className={cx(compact ? "space-y-0.5 pb-1" : "pb-2")}>
                {g.lessons.map((l) => {
                  const current = l.id === currentId;
                  return (
                    <li key={l.id}>
                      <Link href={lessonHref(course.id, l)} aria-current={current ? "page" : undefined}
                        title={l.locked ? "Choose a plan to unlock" : undefined}
                        className={cx("flex items-start gap-2.5 border-l-2 text-sm transition-colors",
                          compact ? "rounded-r-lg py-2 pr-3" : "py-2.5 pr-5",
                          heading ? (compact ? "pl-8" : "pl-11") : (compact ? "pl-3" : "pl-5"),
                          current ? "border-brand-600 bg-brand-50 font-medium text-brand-700" : "border-transparent text-slate-600 hover:bg-slate-50",
                          l.locked && "opacity-60")}>
                        {l.completed ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                          : l.locked ? <Lock className="mt-0.5 size-4 shrink-0 text-slate-400" />
                          : <FileText className={cx("mt-0.5 size-4 shrink-0", current ? "text-brand-600" : "text-slate-400")} />}
                        <span className="flex-1">Lesson {l.number}: {l.title}</span>
                        {!compact && l.has_video && <PlayCircle className="mt-0.5 size-4 shrink-0 text-slate-300" />}
                        {!compact && l.is_free && <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">Free</span>}
                      </Link>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        );
      })}
      {course.lessons.length === 0 && <p className="px-5 py-6 text-sm text-slate-500">No lessons yet.</p>}
    </div>
  );
}
