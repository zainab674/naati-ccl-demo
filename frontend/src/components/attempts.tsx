"use client";

import Link from "next/link";

import { type AttemptSummary, fmtDate } from "@/lib/api";
import { Badge } from "./ui";

export function AttemptList({ items }: { items: AttemptSummary[] }) {
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((a) => (
        <li key={a.id}>
          <Link href={a.status === "in_progress" ? `/attempt/${a.id}` : `/results/${a.id}`}
            className="flex flex-wrap items-center gap-3 px-5 py-3.5 hover:bg-slate-50">
            <Badge tone={a.mode === "mock" ? "violet" : "brand"}>{a.mode === "mock" ? "Mock" : "Practice"}</Badge>
            <span className="flex-1 text-sm font-medium">{a.titles.join(" + ")}</span>
            <span className="text-xs text-slate-500">{fmtDate(a.started_at)}</span>
            {a.status === "in_progress" && <Badge tone="amber">In progress</Badge>}
            {a.status === "marking" && <Badge tone="amber">Marking…</Badge>}
            {a.total !== null && a.status === "marked" && (
              <span className="w-24 text-right text-sm font-semibold tabular-nums">
                {a.total}<span className="font-normal text-slate-400">/{a.total_max}</span>
                <span className={a.passed ? "ml-2 text-emerald-600" : "ml-2 text-rose-600"}>{a.passed ? "●" : "●"}</span>
              </span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  );
}
