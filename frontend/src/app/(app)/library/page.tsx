"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useUser } from "@/components/AppShell";
import { DialogueTable } from "@/components/dialogue";
import LanguagePicker from "@/components/LanguagePicker";
import { Card, cx, PageHeader, Spinner } from "@/components/ui";
import { api, type Activity } from "@/lib/api";

const DOMAINS = ["Health", "Legal", "Financial", "Education", "Community", "Consumer Affairs"];

export default function Library() {
  const { user } = useUser();
  const [items, setItems] = useState<Activity[] | null>(null);
  const [domain, setDomain] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const p = new URLSearchParams();
    if (domain) p.set("domain", domain);
    if (difficulty) p.set("difficulty", difficulty);
    api<Activity[]>(`/activities?${p}`).then(setItems);
  }, [domain, difficulty, user.test_language]);

  const shown = useMemo(() => {
    if (!items) return null;
    const ql = q.trim().toLowerCase();
    return ql ? items.filter((i) => `${i.title} ${i.scenario}`.toLowerCase().includes(ql)) : items;
  }, [items, q]);

  return (
    <div>
      <PageHeader title="Practice dialogues" subtitle="Each dialogue is interpreted segment by segment, with feedback after every segment." />
      <Card className="mb-4 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-56 flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title or scenario"
              className="h-9 w-full rounded-lg border border-slate-300 pl-9 pr-3 text-sm outline-none focus:border-brand-500" />
          </div>
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}
            className="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm">
            <option value="">All difficulties</option>
            <option>Easy</option><option>Moderate</option><option>Hard</option>
          </select>
          {user.role === "student" && <LanguagePicker compact />}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {["", ...DOMAINS].map((d) => (
            <button key={d || "all"} onClick={() => setDomain(d)}
              className={cx("rounded-full px-3 py-1 text-xs font-medium ring-1 transition-colors",
                domain === d ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50")}>
              {d || "All domains"}
            </button>
          ))}
        </div>
      </Card>
      <Card>
        {!shown ? <Spinner /> : shown.length === 0 ? (
          <div className="py-14 text-center text-sm text-slate-500">No dialogues match those filters.</div>
        ) : <DialogueTable items={shown} />}
      </Card>
    </div>
  );
}
