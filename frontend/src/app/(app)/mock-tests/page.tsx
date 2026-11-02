"use client";

import { CheckCircle2, ClipboardCheck, FileText, Lock, RotateCcw } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Button, Card, cx, ErrorNote, inputClass, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { DialogueItem, MockItem } from "@/lib/student";

type Mode = "dialogue" | "full";
type Status = "not_started" | "in_progress" | "completed";

const STATUS: Record<Status, { label: string; className: string }> = {
  not_started: { label: "Not Started", className: "text-slate-500" },
  in_progress: { label: "In Progress", className: "text-amber-700" },
  completed: { label: "Completed", className: "text-emerald-700" },
};

const MODES = [
  { id: "dialogue" as const, icon: FileText, title: "Practice Dialogue (1 dialogue)", text: "Build skills through focused practice with a single dialogue." },
  { id: "full" as const, icon: ClipboardCheck, title: "Full Mock Test (2 dialogues)", text: "Practise two dialogues together under simulated test conditions." },
];

/** One row of Step 2: a dialogue or a mock test, whichever the mode shows. */
type Activity = {
  id: string; title: string; text: string; pills: string[]; difficulty: string; status: Status; locked: boolean; free: boolean;
  inProgressId: string | null; lastAttemptId: string | null; best: string | null; body: { dialogue_id: string } | { mock_test_id: string };
};

const fromDialogue = (d: DialogueItem): Activity => ({
  id: d.id, title: d.title, text: d.description || "Practise one realistic CCL dialogue with feedback and review.",
  pills: d.topic ? [d.topic, d.difficulty] : [d.difficulty], difficulty: d.difficulty, status: d.status, locked: d.locked, free: d.is_free,
  inProgressId: d.in_progress_id, lastAttemptId: d.last_attempt_id, best: d.best_score !== null ? `Best ${d.best_score}/${d.maximum_score}` : null,
  body: { dialogue_id: d.id },
});

const fromMock = (m: MockItem): Activity => ({
  id: m.id, title: m.title, text: m.dialogues.map((d) => d.title).join(" and "),
  pills: [...new Set(m.dialogues.flatMap((d) => (d.topic ? [d.topic, d.difficulty] : [d.difficulty])))],
  difficulty: [...new Set(m.dialogues.map((d) => d.difficulty))].join(" / "), status: m.status, locked: m.locked, free: m.is_free,
  inProgressId: m.in_progress_id, lastAttemptId: m.last_attempt_id, best: m.best_score !== null ? `Best ${m.best_score}/90` : null,
  body: { mock_test_id: m.id },
});

function MockTest() {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState<Mode>(params.get("mode") === "full" ? "full" : "dialogue");
  const [topic, setTopic] = useState(params.get("topic") ?? "");
  const [difficulty, setDifficulty] = useState("");
  const [language, setLanguage] = useState("");
  const [topics, setTopics] = useState<{ id: string; name: string }[]>([]);
  const [dialogues, setDialogues] = useState<DialogueItem[] | null>(null);
  const [mocks, setMocks] = useState<MockItem[] | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState("");

  useEffect(() => { api<{ id: string; name: string }[]>("/topics").then(setTopics).catch(() => {}); }, []);
  useEffect(() => {
    let stale = false; // a slower earlier request must not overwrite a newer filter's results
    api<DialogueItem[]>(`/dialogues?topic=${encodeURIComponent(topic)}&difficulty=${difficulty}&language=${language}`)
      .then((d) => { if (!stale) setDialogues(d); }).catch((e) => setError(e.message));
    return () => { stale = true; };
  }, [topic, difficulty, language]);
  useEffect(() => {
    let stale = false;
    api<MockItem[]>(`/mock-tests?language=${language}`).then((d) => { if (!stale) setMocks(d); }).catch((e) => setError(e.message));
    return () => { stale = true; };
  }, [language]);

  const start = async (a: Activity) => {
    setStarting(a.id);
    try {
      const r = await api<{ id: string }>("/attempts", { method: "POST", json: a.body });
      router.push(`/attempt/${r.id}`);
    } catch (e) { setError((e as Error).message); setStarting(""); }
  };

  // A mock test matches when either of its dialogues does.
  const shownMocks = mocks?.filter((m) => m.dialogues.some((d) => (!topic || d.topic === topic) && (!difficulty || d.difficulty === difficulty)));
  const rows = mode === "dialogue" ? dialogues?.map(fromDialogue) : shownMocks?.map(fromMock);

  return (
    <>
      <PageHeader title="Mock Test" subtitle="Choose a practice mode and an activity to work on."
        actions={<LanguagePicker value={language} onChange={setLanguage} />} />
      <Card className="p-6">
        <h2 className="text-lg font-semibold">Step 1: Choose Your Practice Mode</h2>
        <div role="group" aria-label="Practice mode" className="mt-4 grid gap-4 md:grid-cols-2">
          {MODES.map((m) => {
            const Icon = m.icon;
            const selected = mode === m.id;
            return (
              <button key={m.id} type="button" aria-pressed={selected} onClick={() => setMode(m.id)}
                className={cx("flex flex-col gap-2 rounded-xl border-2 p-5 text-left transition-colors",
                  selected ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white hover:border-brand-200")}>
                <Icon className="size-7 text-brand-600" />
                <span className="text-base font-semibold">{m.title}</span>
                <span className="text-sm text-slate-600">{m.text}</span>
                <span className="mt-2 text-xs font-semibold text-brand-700">{selected ? "✓ Selected" : "Select mode"}</span>
              </button>
            );
          })}
        </div>
      </Card>

      <Card className="mt-6 p-6">
        <h2 className="text-lg font-semibold">Step 2: Choose a {mode === "dialogue" ? "Dialogue" : "Mock Test"} to Practise With</h2>
        <p className="mt-1 text-sm text-slate-500">Browse activities and filter by topic and difficulty.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <label className="block text-sm font-medium text-slate-700">Topic
            <select className={`${inputClass} !w-56`} value={topic} onChange={(e) => setTopic(e.target.value)}>
              <option value="">All topics</option>
              {topics.map((t) => <option key={t.id}>{t.name}</option>)}
            </select></label>
          <label className="block text-sm font-medium text-slate-700">Difficulty
            <select className={`${inputClass} !w-48`} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="">All difficulties</option><option>Easy</option><option>Intermediate</option><option>Difficult</option>
            </select></label>
        </div>
        {error && <div className="mt-4"><ErrorNote>{error}</ErrorNote></div>}
        {!rows ? <Spinner /> : rows.length === 0 ? <p className="mt-5 rounded-lg bg-slate-50 p-8 text-center text-sm text-slate-500">No activities match these filters.</p> : (
          <div className="mt-5 space-y-3">
            {rows.map((a) => <ActivityRow key={a.id} a={a} starting={starting === a.id} onStart={() => start(a)} />)}
          </div>
        )}
      </Card>
    </>
  );
}

function ActivityRow({ a, starting, onStart }: { a: Activity; starting: boolean; onStart: () => void }) {
  const status = STATUS[a.status];
  return (
    <article className="grid items-center gap-3 rounded-xl border border-slate-200 p-4 md:grid-cols-[minmax(0,1fr)_7rem_7rem_11rem]">
      <div className="min-w-0">
        <h3 className="flex items-center gap-2 font-semibold">{a.title}{a.locked && <Lock className="size-4 shrink-0 text-slate-400" />}
          {a.free && <Badge tone="brand">Free</Badge>}</h3>
        <p className="mt-0.5 line-clamp-2 text-sm text-slate-500">{a.text}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">{a.pills.map((p) => <Badge key={p}>{p}</Badge>)}</div>
      </div>
      <div className="text-sm text-slate-500">{a.difficulty}</div>
      <div className={cx("text-sm font-semibold", status.className)}>
        {a.status === "completed" && <CheckCircle2 className="mr-1 inline size-4" />}{status.label}
        {a.best && <div className="text-xs font-normal tabular-nums text-slate-500">{a.best}</div>}
      </div>
      <div className="flex flex-col gap-1.5">
        {a.locked ? <LinkButton href="/pricing" variant="secondary">Unlock</LinkButton>
          : a.inProgressId ? <LinkButton href={`/attempt/${a.inProgressId}`}><RotateCcw className="size-4" /> Continue</LinkButton>
          : a.status === "completed" && a.lastAttemptId ? <>
            <LinkButton href={`/results/${a.lastAttemptId}`}>Review Performance</LinkButton>
            <Button variant="ghost" size="sm" loading={starting} onClick={onStart}>Practise again</Button>
          </> : <Button loading={starting} onClick={onStart}>Start</Button>}
      </div>
    </article>
  );
}

export default function MockTestPage() {
  return <Suspense><MockTest /></Suspense>;
}
