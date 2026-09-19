"use client";

import { Check, Languages } from "lucide-react";
import { useEffect, useState } from "react";

import { api, type Language } from "@/lib/api";
import { useUser } from "./AppShell";
import { Badge, Button, cx, Modal } from "./ui";

let cache: Language[] | null = null;
export function useLanguages() {
  const [langs, setLangs] = useState<Language[] | null>(cache);
  useEffect(() => {
    if (!cache) api<Language[]>("/languages").then((l) => { cache = l; setLangs(l); });
  }, []);
  return langs;
}

function LanguageGrid({ value, onPick }: { value: string | null; onPick: (code: string) => void }) {
  const langs = useLanguages();
  if (!langs) return null;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {langs.map((l) => (
        <button key={l.code} disabled={!l.available} onClick={() => onPick(l.code)}
          className={cx("relative rounded-lg px-3 py-2.5 text-left ring-1 transition-colors",
            value === l.code ? "bg-brand-50 ring-2 ring-brand-500" : "ring-slate-200",
            l.available ? "hover:bg-slate-50" : "cursor-not-allowed opacity-50")}>
          <div className="text-sm font-medium">{l.name}</div>
          <div className="text-sm text-slate-500">{l.native}</div>
          {value === l.code && <Check className="absolute right-2 top-2 size-4 text-brand-600" />}
          {!l.available && <Badge className="absolute right-2 top-2 !text-[10px]">Soon</Badge>}
        </button>
      ))}
    </div>
  );
}

/** Pick (or change) the CCL test language. Opens itself on first login. */
export default function LanguagePicker({ compact }: { compact?: boolean }) {
  const { user, refresh } = useUser();
  const langs = useLanguages();
  const [open, setOpen] = useState(user.role === "student" && !user.test_language);
  const [pick, setPick] = useState<string | null>(user.test_language ?? "hi");
  const [saving, setSaving] = useState(false);
  const current = langs?.find((l) => l.code === (user.test_language ?? "hi"));

  const save = async () => {
    if (!pick) return;
    setSaving(true);
    await api("/me", { method: "PATCH", json: { test_language: pick } });
    await refresh();
    setSaving(false);
    setOpen(false);
  };

  return (
    <>
      <button onClick={() => setOpen(true)}
        className={cx("inline-flex items-center gap-1.5 rounded-full text-sm ring-1 ring-slate-200 hover:bg-slate-50",
          compact ? "px-2.5 py-1" : "bg-white px-3 py-1.5")}>
        <Languages className="size-4 text-brand-600" />
        <span className="font-medium">{current?.name ?? "Hindi"} ↔ English</span>
        <span className="text-slate-400">· change</span>
      </button>
      <Modal open={open} onClose={() => user.test_language && setOpen(false)} title="Which language are you sitting the CCL in?">
        <p className="mb-4 text-sm text-slate-500">
          Every dialogue will be between English and this language. During a test you don&apos;t choose the answer language:
          you always interpret into whichever language the speaker <i>didn&apos;t</i> use.
        </p>
        <LanguageGrid value={pick} onPick={setPick} />
        <div className="mt-5 flex justify-end">
          <Button onClick={save} loading={saving} disabled={!pick}>Continue</Button>
        </div>
      </Modal>
    </>
  );
}
