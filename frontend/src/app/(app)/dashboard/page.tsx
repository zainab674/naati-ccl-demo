"use client";

import {
  ArrowRight, CalendarClock, CalendarDays, ClipboardCheck, Headphones, MessagesSquare, PlayCircle, Target,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { DialogueTable, useStartAttempt } from "@/components/dialogue";
import { AttemptList } from "@/components/attempts";
import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Button, Card, LinkButton, Modal, Spinner } from "@/components/ui";
import { api, type Activity, type AttemptSummary, fmtDate } from "@/lib/api";

type Dash = {
  user: { name: string; exam_date: string | null; days_left: number | null };
  total_practiced: number;
  total_dialogues: number;
  mock: null | { attempt_id: string; total: number; total_max: number; passed: boolean; status: string;
    dialogues: { title: string; score: number }[] };
  in_progress: AttemptSummary | null;
  recent_attempts: AttemptSummary[];
  latest_dialogues: Activity[];
};

export default function Dashboard() {
  const { refresh } = useUser();
  const [d, setD] = useState<Dash | null>(null);
  const [dateOpen, setDateOpen] = useState(false);
  const [dateVal, setDateVal] = useState("");
  const { start, busy } = useStartAttempt();

  const load = () => api<Dash>("/dashboard").then(setD);
  useEffect(() => { load(); }, []);

  if (!d) return <Spinner />;
  const firstName = d.user.name.split(" ")[0];

  const saveDate = async () => {
    await api("/me", { method: "PATCH", json: { exam_date: dateVal || null } });
    setDateOpen(false);
    refresh();
    load();
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back, {firstName}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500">
          <LanguagePicker /> <span>NAATI Credentialed Community Language test</span>
        </div>
      </div>

      {d.in_progress && (
        <Card className="flex flex-wrap items-center justify-between gap-4 border-l-4 border-l-amber-400 p-5">
          <div>
            <div className="text-sm font-medium">You have an unfinished {d.in_progress.mode === "mock" ? "mock test" : "dialogue"}</div>
            <div className="text-sm text-slate-500">{d.in_progress.titles.join(" + ")}</div>
          </div>
          <LinkButton href={`/attempt/${d.in_progress.id}`}>Resume <ArrowRight className="size-4" /></LinkButton>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="p-5">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500"><CalendarClock className="size-4" /> Exam date</div>
          {d.user.exam_date ? (
            <>
              <div className="mt-3 text-3xl font-semibold tabular-nums">{d.user.days_left}<span className="ml-1 text-base font-normal text-slate-500">days to go</span></div>
              <button onClick={() => { setDateVal(d.user.exam_date!); setDateOpen(true); }} className="mt-1 text-sm text-brand-600 hover:underline">{fmtDate(d.user.exam_date)} · change</button>
            </>
          ) : (
            <>
              <div className="mt-3 text-xl font-semibold text-slate-400">Not set</div>
              <button onClick={() => setDateOpen(true)} className="mt-1 text-sm text-brand-600 hover:underline">Set your exam date</button>
            </>
          )}
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500"><Headphones className="size-4" /> Dialogues practised</div>
          <div className="mt-3 text-3xl font-semibold tabular-nums">{d.total_practiced}</div>
          <Link href="/library" className="mt-1 inline-block text-sm text-brand-600 hover:underline">{d.total_dialogues} in the library →</Link>
        </Card>

        <Card className="p-5 sm:col-span-2 lg:col-span-1">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500"><Target className="size-4" /> Last mock test</div>
          {d.mock ? (
            <>
              <div className="mt-3 flex items-baseline gap-3">
                <span className="text-3xl font-semibold tabular-nums">{d.mock.total}<span className="text-base font-normal text-slate-400">/{d.mock.total_max}</span></span>
                <Badge tone={d.mock.passed ? "green" : "red"}>{d.mock.passed ? "Pass" : "Below pass"}</Badge>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                <div className={d.mock.passed ? "h-full bg-emerald-500" : "h-full bg-rose-500"} style={{ width: `${(d.mock.total / d.mock.total_max) * 100}%` }} />
              </div>
              <div className="mt-2 flex justify-between text-xs text-slate-500">
                <span>{d.mock.dialogues.map((x) => x.score).join(" + ")}</span>
                <Link href={`/results/${d.mock.attempt_id}`} className="text-brand-600 hover:underline">See feedback</Link>
              </div>
            </>
          ) : (
            <>
              <div className="mt-3 text-xl font-semibold text-slate-400">0/90</div>
              <Link href="/mock-tests" className="mt-1 inline-block text-sm text-brand-600 hover:underline">Take your first mock →</Link>
            </>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex items-center justify-between gap-4 rounded-xl bg-brand-950 p-6 text-white shadow-sm">
          <div>
            <div className="flex items-center gap-2 text-sm text-brand-200"><ClipboardCheck className="size-4" /> Full exam simulation</div>
            <div className="mt-1 text-lg font-semibold">Mock test · 2 dialogues · marked out of 90</div>
            <div className="mt-1 text-sm text-brand-100/70">Pass needs 63 overall and at least 29 in each dialogue.</div>
          </div>
          <Button variant="secondary" className="shrink-0" loading={busy === "mock-1"} onClick={() => start({ mode: "mock", mock_test_id: "mock-1" })}>Start mock</Button>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {[
            { icon: PlayCircle, title: "Video lessons", text: "Technique tips & walkthroughs" },
            { icon: CalendarDays, title: "Live coaching", text: "Book a session with a tutor" },
            { icon: MessagesSquare, title: "Community", text: "Chat with other candidates" },
            { icon: Target, title: "Vocabulary drills", text: "Domain terms, quick-fire" },
          ].map((s) => (
            <Card key={s.title} className="relative p-4 opacity-75">
              <Badge className="absolute right-3 top-3">Soon</Badge>
              <s.icon className="size-5 text-brand-500" />
              <div className="mt-2 text-sm font-medium">{s.title}</div>
              <div className="text-xs text-slate-500">{s.text}</div>
            </Card>
          ))}
        </div>
      </div>

      <Card>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-semibold">Latest dialogues</h2>
            <p className="text-xs text-slate-500">Newest on top</p>
          </div>
          <Link href="/library" className="text-sm text-brand-600 hover:underline">View all</Link>
        </div>
        <DialogueTable items={d.latest_dialogues} compact />
      </Card>

      <Card>
        <div className="border-b border-slate-100 px-5 py-4"><h2 className="font-semibold">Recent attempts</h2></div>
        {d.recent_attempts.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-slate-500">
            No attempts yet. Pick a dialogue above and interpret your first segment. It takes about five minutes.
          </div>
        ) : (
          <AttemptList items={d.recent_attempts} />
        )}
      </Card>

      <Modal open={dateOpen} onClose={() => setDateOpen(false)} title="When is your CCL test?">
        <div className="space-y-4">
          <input type="date" value={dateVal} onChange={(e) => setDateVal(e.target.value)}
            className="h-10 w-full rounded-lg border border-slate-300 px-3 text-sm" />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDateOpen(false)}>Cancel</Button>
            <Button onClick={saveDate}>Save</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
