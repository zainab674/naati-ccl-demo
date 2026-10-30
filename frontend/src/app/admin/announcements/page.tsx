"use client";

import { Megaphone, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, Card, ErrorNote, Field, inputClass, Modal, PageHeader, Spinner } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api, fetchLanguages, fmtDateTime, type Language } from "@/lib/api";

type Row = { id: string; kind: string; kind_label: string; title: string; body: string; event_at: string | null; link_url: string;
  link_label: string; starts_at: string | null; ends_at: string | null; language: string | null; language_name: string | null;
  status: string; sort_order: number };
type Form = { id?: string; kind: string; title: string; body: string; event_at: string; link_url: string; link_label: string;
  starts_at: string; ends_at: string; language: string; status: string; sort_order: number };

const EMPTY: Form = { kind: "live_session", title: "", body: "", event_at: "", link_url: "", link_label: "", starts_at: "",
  ends_at: "", language: "", status: "Draft", sort_order: 0 };

// <input type="datetime-local"> works in the admin's local time; the API takes ISO timestamps.
const toInput = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const toIso = (v: string) => (v ? new Date(v).toISOString() : null);

function showing(r: Row) {
  const now = Date.now();
  if (r.status !== "Published") return false;
  return (!r.starts_at || new Date(r.starts_at).getTime() <= now) && (!r.ends_at || new Date(r.ends_at).getTime() > now);
}

export default function AdminAnnouncements() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api<Row[]>("/admin/announcements").then(setRows).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); fetchLanguages().then(setLanguages).catch(() => {}); }, [load]);

  const open = (r?: Row) => {
    setError("");
    setForm(r ? { id: r.id, kind: r.kind, title: r.title, body: r.body, event_at: toInput(r.event_at), link_url: r.link_url,
      link_label: r.link_label, starts_at: toInput(r.starts_at), ends_at: toInput(r.ends_at), language: r.language ?? "",
      status: r.status, sort_order: r.sort_order } : EMPTY);
  };
  const set = (patch: Partial<Form>) => form && setForm({ ...form, ...patch });

  const save = async () => {
    if (!form) return;
    setBusy(true);
    setError("");
    const { id, ...f } = form;
    try {
      await api(id ? `/admin/announcements/${id}` : "/admin/announcements", { method: id ? "PUT" : "POST", json: {
        ...f, event_at: toIso(f.event_at), starts_at: toIso(f.starts_at), ends_at: toIso(f.ends_at), language: f.language || null } });
      setForm(null);
      load();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  const remove = async () => {
    if (!form?.id || !confirm(`Delete "${form.title}"?`)) return;
    await api(`/admin/announcements/${form.id}`, { method: "DELETE" }).catch((e) => setError(e.message));
    setForm(null);
    load();
  };

  return (
    <>
      <PageHeader title="Announcements" subtitle="Slides in the carousel at the top of the student dashboard: live group sessions, 1-on-1 classes and news."
        actions={<Button onClick={() => open()}><Plus className="size-4" /> New announcement</Button>} />
      {error && !form && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : rows.length === 0 ? (
        <Card className="p-8 text-center text-sm text-slate-500"><Megaphone className="mx-auto mb-2 size-6" />No announcements yet. The carousel is hidden until one is published.</Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr className="[&>th]:pr-4"><th className="px-5 py-3">Announcement</th><th>Type</th><th>Language</th><th>Shown</th><th>Status</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} onClick={() => open(r)} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-5 py-3"><div className="font-medium">{r.title}</div>
                    {r.event_at && <div className="text-xs text-slate-500">{fmtDateTime(r.event_at)}</div>}</td>
                  <td>{r.kind_label}</td>
                  <td>{r.language_name ?? "Every language"}</td>
                  <td className="text-xs text-slate-500">{r.starts_at ? fmtDateTime(r.starts_at) : "Now"} → {r.ends_at ? fmtDateTime(r.ends_at) : "until hidden"}</td>
                  <td><Badge tone={statusTone(r.status)}>{r.status}</Badge>{showing(r) && <Badge tone="green" className="ml-1">On dashboard</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Edit announcement" : "New announcement"} wide>
        {form && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block"><span className="text-sm font-medium text-slate-700">Type</span>
                <select className={inputClass} value={form.kind} onChange={(e) => set({ kind: e.target.value })}>
                  <option value="live_session">Live session (group)</option><option value="class">1-on-1 class</option><option value="news">News</option>
                </select></label>
              <label className="block"><span className="text-sm font-medium text-slate-700">Language</span>
                <select className={inputClass} value={form.language} onChange={(e) => set({ language: e.target.value })}>
                  <option value="">Every language</option>
                  {languages.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
                </select></label>
            </div>
            <Field label="Title" value={form.title} maxLength={200} onChange={(e) => set({ title: e.target.value })} />
            <label className="block"><span className="text-sm font-medium text-slate-700">Text (optional)</span>
              <textarea className={`${inputClass} min-h-24`} value={form.body} maxLength={1000} onChange={(e) => set({ body: e.target.value })} /></label>
            <Field label="Session date and time (optional)" type="datetime-local" value={form.event_at} onChange={(e) => set({ event_at: e.target.value })}
              hint="Shown on the slide, in each student's own time zone." />
            <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
              <Field label="Link (optional)" value={form.link_url} placeholder="https://zoom.us/j/… or /courses" onChange={(e) => set({ link_url: e.target.value })} />
              <Field label="Button text" value={form.link_label} maxLength={60} placeholder="Join" onChange={(e) => set({ link_label: e.target.value })} />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Show from" type="datetime-local" value={form.starts_at} onChange={(e) => set({ starts_at: e.target.value })} hint="Empty: straight away." />
              <Field label="Hide after" type="datetime-local" value={form.ends_at} onChange={(e) => set({ ends_at: e.target.value })} hint="Empty: until unpublished." />
              <Field label="Order" type="number" value={form.sort_order} onChange={(e) => set({ sort_order: Number(e.target.value) || 0 })} hint="Lower shows first." />
            </div>
            <label className="block"><span className="text-sm font-medium text-slate-700">Status</span>
              <select className={inputClass} value={form.status} onChange={(e) => set({ status: e.target.value })}>
                <option>Draft</option><option>Published</option><option>Archived</option>
              </select></label>
            {error && <ErrorNote>{error}</ErrorNote>}
            <div className="flex justify-between gap-2">
              {form.id ? <Button variant="ghost" onClick={remove}>Delete</Button> : <span />}
              <div className="flex gap-2"><Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button>
                <Button onClick={save} loading={busy} disabled={!form.title.trim()}>Save</Button></div>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
