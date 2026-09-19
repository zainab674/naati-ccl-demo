"use client";

import { CheckCircle2, Clock, Headphones, Mic, Repeat } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useStartAttempt } from "@/components/dialogue";
import { Button, Card, DifficultyBadge, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

type Mock = {
  id: string; title: string;
  dialogues: { title: string; domain: string; difficulty: string }[];
  last_attempt: { id: string; status: string } | null;
};

export default function MockTests() {
  const [mocks, setMocks] = useState<Mock[] | null>(null);
  const { start, busy } = useStartAttempt();
  useEffect(() => { api<Mock[]>("/mock-tests").then(setMocks); }, []);

  return (
    <div>
      <PageHeader title="Mock tests" subtitle="Two dialogues back to back under exam conditions. Feedback comes after you finish." />
      <Card className="mb-6 grid gap-5 p-6 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: Headphones, t: "Each segment plays once", d: "No seek bar and no rewind. The server enforces it, so refreshing won't replay." },
          { icon: Repeat, t: "One repeat per segment", d: "One repeat per dialogue is free. Any more cost marks." },
          { icon: Mic, t: "Interpret after the chime", d: "Recording starts automatically. Press Done when you finish." },
          { icon: CheckCircle2, t: "Pass = 63/90", d: "You also need at least 29/45 in each dialogue." },
        ].map((x) => (
          <div key={x.t}>
            <x.icon className="size-5 text-brand-600" />
            <div className="mt-2 text-sm font-medium">{x.t}</div>
            <div className="mt-0.5 text-sm text-slate-500">{x.d}</div>
          </div>
        ))}
      </Card>
      {!mocks ? <Spinner /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {mocks.map((m) => (
            <Card key={m.id} className="flex flex-col p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">{m.title}</h2>
                <span className="flex items-center gap-1 text-xs text-slate-500"><Clock className="size-3.5" /> ~20 min</span>
              </div>
              <ol className="mt-4 flex-1 space-y-3">
                {m.dialogues.map((d, i) => (
                  <li key={d.title} className="flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2.5">
                    <span className="flex size-6 items-center justify-center rounded-full bg-white text-xs font-semibold ring-1 ring-slate-200">{i + 1}</span>
                    <div className="flex-1">
                      <div className="text-sm font-medium">{d.title}</div>
                      <div className="text-xs text-slate-500">{d.domain}</div>
                    </div>
                    <DifficultyBadge level={d.difficulty} />
                  </li>
                ))}
              </ol>
              <div className="mt-5 flex items-center justify-between">
                {m.last_attempt ? (
                  <Link href={m.last_attempt.status === "in_progress" ? `/attempt/${m.last_attempt.id}` : `/results/${m.last_attempt.id}`}
                    className="text-sm text-brand-600 hover:underline">
                    {m.last_attempt.status === "in_progress" ? "Resume last attempt" : "View last result"}
                  </Link>
                ) : <span className="text-sm text-slate-400">Not attempted</span>}
                <Button loading={busy === m.id} onClick={() => start({ mode: "mock", mock_test_id: m.id })}>
                  {m.last_attempt?.status === "in_progress" ? "Resume" : "Start mock test"}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
