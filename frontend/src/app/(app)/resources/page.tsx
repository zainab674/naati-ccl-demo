"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Card, cx, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { fileSize, RESOURCE_TYPES, type ResourceItem, TYPE_ICON, TYPE_LABEL } from "@/lib/resources";

export default function LearningHub() {
  const [items, setItems] = useState<ResourceItem[] | null>(null);
  const [type, setType] = useState("");
  const [language, setLanguage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let stale = false; // a slower earlier request must not overwrite a newer filter's results
    api<ResourceItem[]>(`/resources?type=${type}&language=${language}`).then((d) => { if (!stale) setItems(d); }).catch((e) => setError(e.message));
    return () => { stale = true; };
  }, [type, language]);

  const chip = (active: boolean) => cx("rounded-full px-3 py-1 text-sm", active ? "bg-brand-600 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50");
  return (
    <>
      <PageHeader title="Learning hub" subtitle="Ebooks, glossaries, worksheets and other study resources."
        actions={<LanguagePicker value={language} onChange={setLanguage} />} />
      <div className="mb-6 flex flex-wrap gap-2">
        <button className={chip(!type)} onClick={() => setType("")}>Everything</button>
        {RESOURCE_TYPES.map((t) => <button key={t} className={chip(type === t)} onClick={() => setType(t)}>{TYPE_LABEL[t]}</button>)}
      </div>
      {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}
      {!items ? <Spinner /> : items.length === 0 ? <Card className="p-6 text-sm text-slate-500">No resources here yet.</Card> : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((r) => {
            const Icon = TYPE_ICON[r.type];
            return (
              <Link key={r.id} href={r.locked ? "/pricing" : `/resources/${r.id}`}>
                <Card className="flex h-full flex-col p-5 transition-shadow hover:shadow-md">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="flex items-start gap-2 font-semibold leading-snug"><Icon className="mt-0.5 size-4 shrink-0 text-brand-600" />{r.title}</h3>
                    {r.locked ? <Lock className="size-4 shrink-0 text-slate-400" /> : r.is_free ? <Badge tone="brand">Free</Badge> : null}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Badge>{r.type}</Badge>
                    {r.language_name && <Badge tone="violet">{r.language_name}</Badge>}
                    {r.topic && <Badge>{r.topic}</Badge>}
                  </div>
                  {r.description && <p className="mt-3 line-clamp-3 text-sm text-slate-600">{r.description}</p>}
                  <div className="mt-auto pt-4 text-xs text-slate-500">
                    {r.locked ? <span className="font-medium text-brand-600">Unlock with a plan</span>
                      : r.has_file ? `${r.file_name.split(".").pop()?.toUpperCase()} · ${fileSize(r.file_size)}` : r.has_link ? "External link" : "Read online"}
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
