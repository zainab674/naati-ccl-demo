"use client";

import { useEffect, useState } from "react";

import { Badge, Button, Card, ErrorNote, Field, inputClass, Modal, PageHeader, Spinner } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api } from "@/lib/api";

type Mock = { id: string; key: string; title: string; status: string; is_free: boolean; sort_order: number;
  dialogues: { id: string; title: string; status: string }[] };
type DialogueOpt = { id: string; title: string; status: string };
type Form = { id?: string; key: string; title: string; dialogue_ids: string[]; status: string; is_free: boolean; sort_order: number };

const EMPTY: Form = { key: "", title: "", dialogue_ids: ["", ""], status: "Draft", is_free: false, sort_order: 0 };

export default function AdminMockTests() {
  const [mocks, setMocks] = useState<Mock[] | null>(null);
  const [dialogues, setDialogues] = useState<DialogueOpt[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api<Mock[]>("/admin/mock-tests").then(setMocks).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    api<DialogueOpt[]>("/admin/dialogues").then((d) => setDialogues(d.filter((x) => x.status !== "Archived"))).catch(() => {});
  }, []);

  const save = async () => {
    if (!form) return;
    setBusy(true);
    setError("");
    try {
      const { id, ...body } = form;
      await api(id ? `/admin/mock-tests/${id}` : "/admin/mock-tests", { method: id ? "PUT" : "POST", json: body });
      setForm(null);
      load();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <>
      <PageHeader title="Mock tests" subtitle="A mock test is two dialogues, scored out of 90."
        actions={<Button onClick={() => { setError(""); setForm(EMPTY); }}>New mock test</Button>} />
      {error && !form && <ErrorNote>{error}</ErrorNote>}
      {!mocks ? <Spinner /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {mocks.map((m) => (
            <Card key={m.id} className="p-5" onClick={() => {
              setError("");
              setForm({ id: m.id, key: m.key, title: m.title, status: m.status, is_free: m.is_free, sort_order: m.sort_order, dialogue_ids: m.dialogues.map((d) => d.id) });
            }}>
              <div className="flex items-start justify-between gap-3">
                <div><div className="font-semibold">{m.title}</div><div className="font-mono text-xs text-slate-400">{m.key}</div></div>
                <div className="space-x-1"><Badge tone={statusTone(m.status)}>{m.status}</Badge>{m.is_free && <Badge tone="brand">Free</Badge>}</div>
              </div>
              <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
                {m.dialogues.map((d) => <li key={d.id}>{d.title} {d.status !== "Published" && <Badge tone="amber">{d.status}</Badge>}</li>)}
              </ol>
            </Card>
          ))}
          {mocks.length === 0 && <Card className="p-6 text-sm text-slate-500">No mock tests yet.</Card>}
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Edit mock test" : "New mock test"}>
        {form && (
          <div className="space-y-4">
            <Field label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <Field label="Key" value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value.toLowerCase() })} hint="Lowercase letters, numbers and dashes." />
            {[0, 1].map((i) => (
              <label key={i} className="block"><span className="text-sm font-medium text-slate-700">Dialogue {i + 1}</span>
                <select className={inputClass} value={form.dialogue_ids[i] ?? ""} onChange={(e) => {
                  const ids = [...form.dialogue_ids]; ids[i] = e.target.value; setForm({ ...form, dialogue_ids: ids });
                }}>
                  <option value="">Choose a dialogue</option>
                  {dialogues.map((d) => <option key={d.id} value={d.id}>{d.title}{d.status !== "Published" ? ` (${d.status})` : ""}</option>)}
                </select></label>
            ))}
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="text-sm font-medium text-slate-700">Status</span>
                <select className={inputClass} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  <option>Draft</option><option>Published</option><option>Archived</option>
                </select></label>
              <Field label="Sort order" type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_free} onChange={(e) => setForm({ ...form, is_free: e.target.checked })} className="accent-brand-600" /> Free mock test</label>
            {error && <ErrorNote>{error}</ErrorNote>}
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button><Button onClick={save} loading={busy}>Save</Button></div>
          </div>
        )}
      </Modal>
    </>
  );
}
