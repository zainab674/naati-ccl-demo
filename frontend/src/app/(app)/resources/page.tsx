"use client";

import { Lock } from "lucide-react";
import { useEffect, useState } from "react";

import CoverImage from "@/components/CoverImage";
import LanguagePicker from "@/components/LanguagePicker";
import { Badge, Card, cx, ErrorNote, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { fileSize, RESOURCE_TYPES, type ResourceItem, TYPE_LABEL } from "@/lib/resources";

export default function Resources() {
  const [items, setItems] = useState<ResourceItem[] | null>(null);
  const [type, setType] = useState("");
  const [language, setLanguage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let stale = false; // a slower earlier request must not overwrite a newer filter's results
    api<ResourceItem[]>(`/resources?type=${type}&language=${language}`).then((d) => { if (!stale) setItems(d); }).catch((e) => setError(e.message));
    return () => { stale = true; };
  }, [type, language]);

  const chip = (active: boolean) => cx("rounded-full border px-3.5 py-2 text-xs", active ? "border-brand-600 bg-brand-600 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50");
  return (
    <>
      <PageHeader title="Resources" subtitle="Ebooks, glossaries, worksheets and other study resources." />
      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Resource Library</h2>
            <p className="text-sm text-slate-500">Find materials to support your interpreting practice.</p>
          </div>
          <LanguagePicker value={language} onChange={setLanguage} />
        </div>
        <div className="my-5 flex flex-wrap gap-2">
          <button className={chip(!type)} onClick={() => setType("")}>Everything</button>
          {RESOURCE_TYPES.map((t) => <button key={t} className={chip(type === t)} onClick={() => setType(t)}>{TYPE_LABEL[t]}</button>)}
        </div>
        {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}
        {!items ? <Spinner /> : items.length === 0 ? <p className="rounded-lg bg-slate-50 p-8 text-center text-sm text-slate-500">No resources match these filters.</p> : (
          <div className="space-y-3.5">
            {items.map((r) => (
              <article key={r.id} className="grid items-center gap-4 rounded-xl border border-slate-200 p-4 grid-cols-[4.5rem_minmax(0,1fr)] sm:grid-cols-[6rem_minmax(0,1fr)_auto]">
                <div className="h-24 w-[4.5rem] overflow-hidden rounded sm:h-32 sm:w-24">
                  <CoverImage src={r.image_url} title={r.title} seed={r.id} kicker="BENCHMARK CCL" small />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-brand-600">{r.type}
                    {r.locked && <Lock className="size-3.5 text-slate-400" />}{r.is_free && <Badge tone="brand">Free</Badge>}</div>
                  <h3 className="mt-1 text-base font-semibold">{r.title}</h3>
                  {r.description && <p className="mt-0.5 line-clamp-2 text-sm text-slate-500">{r.description}</p>}
                  <div className="mt-1 text-xs text-slate-500">{r.language_name ?? "All languages"}{r.topic ? ` · ${r.topic}` : ""}
                    {!r.locked && r.has_file ? ` · ${r.file_name.split(".").pop()?.toUpperCase()} ${fileSize(r.file_size)}` : ""}</div>
                </div>
                <div className="col-start-2 sm:col-start-auto">
                  <LinkButton variant="secondary" href={r.locked ? "/pricing" : `/resources/${r.id}`}>{r.locked ? "Unlock" : r.type === "Link" ? "Open Link" : "View Resource"}</LinkButton>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
