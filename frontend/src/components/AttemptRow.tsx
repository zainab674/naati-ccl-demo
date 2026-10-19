import Link from "next/link";

import { fmtDate } from "@/lib/api";
import type { AttemptSummary } from "@/lib/student";
import { Badge } from "./ui";

export function attemptHref(a: AttemptSummary) {
  return a.status === "In Progress" ? `/attempt/${a.id}` : `/results/${a.id}`;
}

export default function AttemptRow({ a }: { a: AttemptSummary }) {
  const scored = a.total_score !== null;
  return (
    <Link href={attemptHref(a)} className="flex items-center justify-between gap-4 px-5 py-3 hover:bg-slate-50">
      <div className="min-w-0">
        <div className="truncate font-medium">{a.title}</div>
        <div className="text-xs text-slate-500">
          {a.kind === "mock" ? "Mock test" : "Practice"} · {a.started_at ? fmtDate(a.started_at) : ""} · {a.answered}/{a.segments} segments answered
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {a.status === "In Progress" ? <Badge tone="amber">In progress</Badge>
          : scored ? (
            <>
              <span className="text-sm font-semibold tabular-nums">{a.total_score}/{a.maximum_score}</span>
              {a.result && <Badge tone={a.result === "Pass" ? "green" : "red"}>{a.result}</Badge>}
            </>
          ) : <Badge tone={a.scoring_status === "Failed" ? "red" : "slate"}>{a.scoring_status === "Failed" ? "Scoring failed" : "Scoring…"}</Badge>}
      </div>
    </Link>
  );
}
