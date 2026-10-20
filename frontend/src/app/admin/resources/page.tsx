"use client";

import { Upload } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, Card, cx, ErrorNote, Field, inputClass, Modal, PageHeader, Spinner } from "@/components/ui";
import { statusTone } from "@/lib/admin";
import { api, fetchLanguages, fmtDate, type Language } from "@/lib/api";
import { fileSize, RESOURCE_TYPES, type ResourceItem, type ResourceType } from "@/lib/resources";

type AdminResource = ResourceItem & { key: string; status: string; sort_order: number; external_url: string; html_content: string;
  updated_at: string; problems: string[] };
type Form = { id?: string; key: string; title: string; description: string; type: ResourceType; language: string; topic: string;
  is_free: boolean; sort_order: number; external_url: string; html_content: string };

const EMPTY: Form = { key: "", title: "", description: "", type: "Ebook", language: "", topic: "", is_free: false, sort_order: 0,
  external_url: "", html_content: "" };

const HELP: Record<ResourceType, string> = {
  Ebook: "Upload a PDF or EPUB.", Glossary: "Upload a PDF, Word or Excel file, or link to one.", Worksheet: "Upload a PDF or Word file.",
  Audio: "Upload an MP3, M4A or WAV file.", Video: "Upload an MP4, or give a video URL.", Article: "Write the article text below.",
  Link: "Give the URL of the page.",
};

export default function AdminResources() {
  const [rows, setRows] = useState<AdminResource[] | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [current, setCurrent] = useState<AdminResource | null>(null);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [topics, setTopics] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = () => api<AdminResource[]>("/admin/resources").then(setRows).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    fetchLanguages().then(setLanguages).catch(() => {});
    api<{ id: string; name: string }[]>("/topics").then(setTopics).catch(() => {});
  }, []);

  const open = (r?: AdminResource) => {
    setError("");
    setCurrent(r ?? null);
    setForm(r ? { id: r.id, key: r.key, title: r.title, description: r.description, type: r.type, language: r.language ?? "",
      topic: r.topic ?? "", is_free: r.is_free, sort_order: r.sort_order, external_url: r.external_url, html_content: r.html_content } : EMPTY);
  };

  const save = async (status?: string) => {
    if (!form) return;
    setBusy(status ?? "save");
    setError("");
    try {
      const { id, ...body } = form;
      const json = { ...body, language: body.language || null, topic: body.topic || null, ...(status ? { status } : {}) };
      const r = await api<AdminResource>(id ? `/admin/resources/${id}` : "/admin/resources", { method: id ? "PATCH" : "POST", json });
      setCurrent(r);
      setForm({ ...form, id: r.id });
      load();
    } catch (e) { setError((e as Error).message); }
    setBusy("");
  };

  const upload = async (file: File) => {
    if (!current) return;
    setBusy("upload");
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    try { setCurrent(await api<AdminResource>(`/admin/resources/${current.id}/file`, { method: "POST", body: fd })); load(); }
    catch (e) { setError((e as Error).message); }
    setBusy("");
  };

  const removeFile = async () => {
    if (!current) return;
    setBusy("remove");
    setError("");
    try { setCurrent(await api<AdminResource>(`/admin/resources/${current.id}/file`, { method: "DELETE" })); load(); }
    catch (e) { setError((e as Error).message); }
    setBusy("");
  };

  return (
    <>
      <PageHeader title="Learning hub" subtitle="Ebooks, glossaries, worksheets, audio, video, articles and links for students."
        actions={<Button onClick={() => open()}>New resource</Button>} />
      {error && !form && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="px-5 py-3">Resource</th><th>Type</th><th>Language</th><th>Content</th><th>Status</th><th>Updated</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => open(r)}>
                  <td className="px-5 py-3"><div className="font-medium">{r.title}</div><div className="font-mono text-xs text-slate-400">{r.key}</div></td>
                  <td>{r.type}</td>
                  <td>{r.language_name ?? "All"}</td>
                  <td className="text-slate-600">{r.has_file ? `${r.file_name} (${fileSize(r.file_size)})` : r.has_link ? "Link" : r.html_content ? "Article text" : <Badge tone="amber">No content</Badge>}</td>
                  <td className="space-x-1"><Badge tone={statusTone(r.status)}>{r.status}</Badge>{r.is_free && <Badge tone="brand">Free</Badge>}</td>
                  <td>{fmtDate(r.updated_at)}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={6} className="px-5 py-6 text-slate-500">No resources yet.</td></tr>}
            </tbody>
          </table>
        </Card>
      )}

      <Modal open={!!form} onClose={() => { setForm(null); setCurrent(null); }} title={form?.id ? "Edit resource" : "New resource"} wide>
        {form && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
              <Field label="Key" value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value.toLowerCase() })} hint="Lowercase letters, numbers and dashes." />
              <label className="block"><span className="text-sm font-medium text-slate-700">Type</span>
                <select className={inputClass} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as ResourceType })}>
                  {RESOURCE_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select></label>
              <label className="block"><span className="text-sm font-medium text-slate-700">Language</span>
                <select className={inputClass} value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
                  <option value="">All languages</option>
                  {languages.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
                </select></label>
              <label className="block"><span className="text-sm font-medium text-slate-700">Topic (optional)</span>
                <select className={inputClass} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })}>
                  <option value="">None</option>
                  {topics.map((t) => <option key={t.id}>{t.name}</option>)}
                </select></label>
              <Field label="Sort order" type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
            </div>
            <label className="block"><span className="text-sm font-medium text-slate-700">Description</span>
              <textarea dir="auto" className={cx(inputClass, "h-20 py-2")} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
            <p className="text-sm text-slate-600">{HELP[form.type]}</p>
            {form.type !== "Article" && <Field label="External URL (optional for files)" value={form.external_url} placeholder="https://"
              onChange={(e) => setForm({ ...form, external_url: e.target.value })} />}
            {form.type === "Article" && <label className="block"><span className="text-sm font-medium text-slate-700">Article (HTML; unsafe tags are removed)</span>
              <textarea dir="auto" className={cx(inputClass, "h-48 py-2 font-mono text-xs")} value={form.html_content} onChange={(e) => setForm({ ...form, html_content: e.target.value })} /></label>}
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_free} onChange={(e) => setForm({ ...form, is_free: e.target.checked })} className="accent-brand-600" /> Free for every signed-in student</label>

            {current && form.type !== "Article" && form.type !== "Link" && (
              <div className="rounded-lg bg-slate-50 p-4 text-sm">
                <div className="font-medium">File</div>
                {current.has_file
                  ? <div className="mt-1 flex flex-wrap items-center gap-3"><a href={`/api/admin/resources/${current.id}/file`} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">{current.file_name}</a>
                      <span className="text-slate-500">{fileSize(current.file_size)}</span>
                      <Button size="sm" variant="ghost" loading={busy === "remove"} onClick={removeFile}>Remove</Button></div>
                  : <p className="mt-1 text-slate-500">No file uploaded yet.</p>}
                <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg bg-white px-3 py-2 font-medium ring-1 ring-slate-200 hover:bg-slate-100">
                  <Upload className="size-4" /> {busy === "upload" ? "Uploading..." : current.has_file ? "Replace file" : "Upload file"}
                  <input type="file" className="hidden" accept=".pdf,.epub,.docx,.xlsx,.pptx,.mp3,.m4a,.wav,.mp4,.png,.jpg,.jpeg"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
                </label>
              </div>
            )}
            {!current && form.type !== "Article" && form.type !== "Link" && <p className="text-xs text-slate-500">Save first, then upload the file.</p>}
            {current && current.problems.length > 0 && <p className="text-xs text-amber-700">Before publishing: {current.problems.join("; ")}</p>}
            {error && <ErrorNote>{error}</ErrorNote>}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>{current && <Badge tone={statusTone(current.status)}>{current.status}</Badge>}</div>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => { setForm(null); setCurrent(null); }}>Close</Button>
                <Button variant="secondary" onClick={() => save()} loading={busy === "save"}>Save</Button>
                {current?.status === "Published"
                  ? <Button variant="secondary" onClick={() => save("Archived")} loading={busy === "Archived"}>Hide</Button>
                  : current && <Button onClick={() => save("Published")} loading={busy === "Published"}>Publish</Button>}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
