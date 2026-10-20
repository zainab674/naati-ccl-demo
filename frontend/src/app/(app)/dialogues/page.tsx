"use client";

import { CheckCircle2, Clock, Lock, PlayCircle, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Button, Card, cx, DifficultyBadge, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { type DialogueItem, minutes } from "@/lib/student";

const STATUS = {
  not_started: { label: "Not started", tone: "slate" as const },
  in_progress: { label: "In progress", tone: "amber" as const },
  completed: { label: "Completed", tone: "green" as const },
};

export default function LibraryPage() {
  const router = useRouter();
  const [items, setItems] = useState<DialogueItem[] | null>(null);
  const [topics, setTopics] = useState<{ id: string; name: string }[]>([]);
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [language, setLanguage] = useState("");
  const [error, setError] = useState("");
  const [starting, setStarting] = useState("");

  useEffect(() => { api<{ id: string; name: string }[]>("/topics").then(setTopics).catch(() => {}); }, []);
  useEffect(() => {
    let stale = false; // a slower earlier request must not overwrite a newer filter's results
    api<DialogueItem[]>(`/dialogues?topic=${encodeURIComponent(topic)}&difficulty=${difficulty}&language=${language}`)
      .then((d) => { if (!stale) setItems(d); }).catch((e) => setError(e.message));
    return () => { stale = true; };
  }, [topic, difficulty, language]);

  const start = async (d: DialogueItem) => {
    if (d.in_progress_id) { router.push(`/attempt/${d.in_progress_id}`); return; }
    setStarting(d.id);
    try {
      const r = await api<{ id: string }>("/attempts", { method: "POST", json: { dialogue_id: d.id } });
      router.push(`/attempt/${r.id}`);
    } catch (e) { setError((e as Error).message); setStarting(""); }
  };

  const chip = (active: boolean) => cx("rounded-full px-3 py-1 text-sm", active ? "bg-brand-600 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50");

  return (
    <>
      <PageHeader title="Practice dialogues" subtitle="Interpret between English and your language. Each dialogue is scored out of 45."
        actions={<LanguagePicker value={language} onChange={setLanguage} />} />
      <div className="mb-3 flex flex-wrap gap-2">
        <button className={chip(!topic)} onClick={() => setTopic("")}>All topics</button>
        {topics.map((t) => <button key={t.id} className={chip(topic === t.name)} onClick={() => setTopic(t.name)}>{t.name}</button>)}
      </div>
      <div className="mb-6 flex flex-wrap gap-2">
        {["", "Easy", "Intermediate", "Difficult"].map((d) => <button key={d} className={chip(difficulty === d)} onClick={() => setDifficulty(d)}>{d || "Any difficulty"}</button>)}
      </div>
      {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}
      {!items ? <Spinner /> : items.length === 0 ? <Card className="p-6 text-sm text-slate-500">No dialogues match these filters yet. Try another topic, difficulty or language.</Card> : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((d) => (
            <Card key={d.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold leading-snug">{d.title}</h3>
                {d.locked ? <Lock className="size-4 shrink-0 text-slate-400" /> : d.status === "completed" ? <CheckCircle2 className="size-4 shrink-0 text-emerald-600" /> : null}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {language === "all" && <Badge tone="violet">{d.language_name}</Badge>}
                {d.topic && <Badge>{d.topic}</Badge>}
                <DifficultyBadge level={d.difficulty} />
                {d.is_free && <Badge tone="brand">Free</Badge>}
              </div>
              {d.description && <p className="mt-3 line-clamp-2 text-sm text-slate-600">{d.description}</p>}
              <div className="mt-3 flex items-center gap-3 text-xs text-slate-500">
                <span>{d.segments} segments</span>
                {d.estimated_duration ? <span className="inline-flex items-center gap-1"><Clock className="size-3" />{minutes(d.estimated_duration)}</span> : null}
              </div>
              <div className="mt-auto flex items-center justify-between pt-5">
                <div className="text-sm">
                  <Badge tone={STATUS[d.status].tone}>{STATUS[d.status].label}</Badge>
                  {d.best_score !== null && <span className="ml-2 tabular-nums text-slate-600">Best {d.best_score}/{d.maximum_score}</span>}
                </div>
                {d.locked ? <Link href="/pricing" className="text-sm font-medium text-brand-600 hover:underline">Unlock</Link>
                  : <Button size="sm" variant={d.status === "in_progress" ? "primary" : "secondary"} loading={starting === d.id} onClick={() => start(d)}>
                    {d.status === "in_progress" ? <><RotateCcw className="size-4" /> Continue</> : <><PlayCircle className="size-4" /> {d.status === "completed" ? "Practise again" : "Start"}</>}
                  </Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
