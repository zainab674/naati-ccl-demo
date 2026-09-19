"use client";

import { CheckCircle2, Loader2, Plus, Wand2, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Card, DifficultyBadge, ErrorNote, Modal, PageHeader } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

type Row = { id: string; number: number; title: string; domain: string; difficulty: string; status: string;
  status_detail: string; segment_count: number; created_at: string };

const SAMPLE = `EN: Good afternoon. I'm calling from the council about your application for a disabled parking permit.
REF: नमस्ते। मैं काउंसिल से आपके विकलांग पार्किंग परमिट के आवेदन के बारे में बात करने के लिए फ़ोन कर रही हूँ।
HI: जी नमस्ते। मैंने तीन हफ़्ते पहले फ़ॉर्म भरा था, पर अभी तक कोई जवाब नहीं आया।
REF: Hello. I filled in the form three weeks ago, but I still haven't heard anything back.
EN: I'm sorry about the delay. We still need a letter from your doctor confirming that you can't walk more than 100 metres.
REF: देरी के लिए माफ़ी चाहती हूँ। हमें अभी भी आपके डॉक्टर का एक पत्र चाहिए जिसमें लिखा हो कि आप 100 मीटर से ज़्यादा नहीं चल सकते।
HI: ठीक है, मैं कल ही डॉक्टर से मिलकर पत्र ले लूँगा। क्या मैं उसे ईमेल कर सकता हूँ?
REF: Okay, I'll see the doctor tomorrow and get the letter. Can I email it to you?`;

const EMPTY = {
  title: "", scenario: "", domain: "", difficulty: "", en_role: "", en_gender: "female", hi_role: "", hi_gender: "male", script: "",
};
const EXAMPLE = {
  title: "Disabled Parking Permit", scenario: "A council officer follows up on a resident's disabled parking permit application.",
  domain: "Community", difficulty: "Easy", en_role: "Council officer", en_gender: "female", hi_role: "Resident", hi_gender: "male", script: SAMPLE,
};
const PLACEHOLDER_SCRIPT = `EN: English speaker's segment
REF: Model Hindi interpretation
HI: Hindi speaker's segment
REF: Model English interpretation`;

const input = "h-10 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-brand-500";

export default function ContentStudio() {
  const [rows, setRows] = useState<Row[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const load = useCallback(() => api<Row[]>("/admin/activities").then(setRows), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!rows.some((r) => r.status === "processing")) return;
    const t = setTimeout(load, 1500);
    return () => clearTimeout(t);
  }, [rows, load]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const submit = async () => {
    setBusy(true);
    setErr("");
    try {
      await api("/admin/activities", { method: "POST", json: form });
      await load();
      setForm(EMPTY);
      setOpen(false);
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  };

  return (
    <div>
      <PageHeader title="Content studio"
        subtitle="Paste a dialogue script. The platform voices it, adds the chime, encrypts and segments the audio, and publishes it to the library. No developer needed."
        actions={<Button onClick={() => { setErr(""); setForm(EMPTY); setOpen(true); }}><Plus className="size-4" /> New dialogue</Button>} />
        <Card>
          <div className="border-b border-slate-100 px-5 py-4"><h2 className="font-semibold">Library</h2><p className="text-xs text-slate-500">{rows.length} dialogues{rows.some((r) => r.status === "processing") ? " · generating audio…" : ""}</p></div>
          <ul className="divide-y divide-slate-100">
            {rows.map((r) => (
              <li key={r.id} className="px-5 py-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium"><span className="text-slate-400">#{r.number}</span> {r.title}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">{r.domain} · {r.segment_count} seg <DifficultyBadge level={r.difficulty} /></div>
                  </div>
                  {r.status === "published" ? <Badge tone="green"><CheckCircle2 className="size-3" /> Live</Badge> :
                    r.status === "processing" ? <Badge tone="amber"><Loader2 className="size-3 animate-spin" /> Generating</Badge> :
                    <Badge tone="red"><XCircle className="size-3" /> Failed</Badge>}
                </div>
                {r.status_detail && <div className="mt-1 text-xs text-slate-500">{r.status_detail}</div>}
                <div className="mt-0.5 text-[11px] text-slate-400">{fmtDateTime(r.created_at)}</div>
              </li>
            ))}
          </ul>
        </Card>

      <Modal open={open} onClose={() => !busy && setOpen(false)} title="New dialogue" wide>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="sm:col-span-2"><span className="text-sm font-medium">Title</span><input className={input} value={form.title} onChange={set("title")} placeholder="e.g. Rental Bond Dispute" /></label>
            <label className="sm:col-span-2"><span className="text-sm font-medium">Scenario</span><input className={input} value={form.scenario} onChange={set("scenario")} placeholder="One sentence describing who is talking and why" /></label>
            <label><span className="text-sm font-medium">Domain</span>
              <select className={input} value={form.domain} onChange={set("domain")}>
                <option value="" disabled>Select domain</option>
                {["Health", "Legal", "Financial", "Education", "Community", "Consumer Affairs", "Immigration", "Housing", "Employment"].map((d) => <option key={d}>{d}</option>)}
              </select></label>
            <label><span className="text-sm font-medium">Difficulty</span>
              <select className={input} value={form.difficulty} onChange={set("difficulty")}><option value="" disabled>Select difficulty</option><option>Easy</option><option>Moderate</option><option>Hard</option></select></label>
            <label><span className="text-sm font-medium">English speaker role</span><input className={input} value={form.en_role} onChange={set("en_role")} placeholder="e.g. Doctor, Bank officer" /></label>
            <label><span className="text-sm font-medium">Voice</span>
              <select className={input} value={form.en_gender} onChange={set("en_gender")}><option value="female">Female (en-AU)</option><option value="male">Male (en-AU)</option></select></label>
            <label><span className="text-sm font-medium">Hindi speaker role</span><input className={input} value={form.hi_role} onChange={set("hi_role")} placeholder="e.g. Patient, Customer" /></label>
            <label><span className="text-sm font-medium">Voice</span>
              <select className={input} value={form.hi_gender} onChange={set("hi_gender")}><option value="male">Male (hi-IN)</option><option value="female">Female (hi-IN)</option></select></label>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium">Script</span>
            <span className="ml-2 text-xs text-slate-500">One line per segment: <code>EN:</code> or <code>HI:</code>, each followed by a <code>REF:</code> model interpretation</span>
            <button type="button" onClick={() => setForm(EXAMPLE)} className="ml-2 text-xs text-brand-600 hover:underline">Insert example</button>
            <textarea value={form.script} onChange={set("script")} rows={12} placeholder={PLACEHOLDER_SCRIPT}
              className="hindi mt-1 w-full rounded-lg border border-slate-300 p-3 font-mono text-[13px] leading-relaxed outline-none focus:border-brand-500" />
          </label>
          {err && <div className="mt-3"><ErrorNote>{err}</ErrorNote></div>}
          <div className="mt-4 flex justify-end">
            <Button onClick={submit} loading={busy}
              disabled={!form.title.trim() || !form.domain || !form.difficulty || !form.en_role.trim() || !form.hi_role.trim() || !form.script.trim()}><Wand2 className="size-4" /> Generate &amp; publish</Button>
          </div>
              </Modal>
    </div>
  );
}
