"use client";

import { ClipboardCheck, Lock, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Button, Card, DifficultyBadge, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { MockItem } from "@/lib/student";

export default function MockTestsPage() {
  const router = useRouter();
  const [items, setItems] = useState<MockItem[] | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState("");
  const [language, setLanguage] = useState("");

  useEffect(() => {
    let stale = false;
    api<MockItem[]>(`/mock-tests?language=${language}`).then((d) => { if (!stale) setItems(d); }).catch((e) => setError(e.message));
    return () => { stale = true; };
  }, [language]);

  const start = async (m: MockItem) => {
    if (m.in_progress_id) { router.push(`/attempt/${m.in_progress_id}`); return; }
    setStarting(m.id);
    try {
      const r = await api<{ id: string }>("/attempts", { method: "POST", json: { mock_test_id: m.id } });
      router.push(`/attempt/${r.id}`);
    } catch (e) { setError((e as Error).message); setStarting(""); }
  };

  return (
    <>
      <PageHeader title="Mock tests" subtitle="Two dialogues in the official test format. Pass mark 63/90 with at least 29 in each dialogue."
        actions={<LanguagePicker value={language} onChange={setLanguage} />} />
      {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}
      {!items ? <Spinner /> : items.length === 0 ? <Card className="p-6 text-sm text-slate-500">No mock tests are available yet.</Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((m) => (
            <Card key={m.id} className="flex flex-col p-6">
              <div className="flex items-start justify-between">
                <h3 className="flex items-center gap-2 text-lg font-semibold"><ClipboardCheck className="size-5 text-brand-600" />{m.title}</h3>
                {m.locked ? <Lock className="size-4 text-slate-400" /> : m.is_free ? <Badge tone="brand">Free</Badge> : null}
              </div>
              <ol className="mt-4 space-y-2 text-sm">
                {m.dialogues.map((d, i) => (
                  <li key={i} className="flex items-center justify-between gap-2">
                    <span><span className="mr-2 text-slate-400">{i + 1}.</span>{d.title}</span>
                    <DifficultyBadge level={d.difficulty} />
                  </li>
                ))}
              </ol>
              <div className="mt-auto flex items-center justify-between pt-6 text-sm">
                <span className="text-slate-500">{m.attempts ? `${m.attempts} attempt${m.attempts > 1 ? "s" : ""}` : "Not attempted"}{m.best_score !== null && ` · best ${m.best_score}/90`}</span>
                {m.locked ? <Link href="/pricing" className="font-medium text-brand-600 hover:underline">Unlock</Link>
                  : <Button loading={starting === m.id} onClick={() => start(m)}>{m.in_progress_id ? <><RotateCcw className="size-4" /> Continue</> : "Start mock test"}</Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
