"use client";

import { Mail, Upload, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import CsvFormatButtons from "@/components/CsvFormatButtons";
import ImportReport, { type ImportJob } from "@/components/ImportReport";
import { useUser } from "@/components/AppShell";
import MessageStudents from "@/components/MessageStudents";
import TeacherSelect, { type Teacher, useTeachers } from "@/components/TeacherSelect";
import { Badge, Button, Card, ErrorNote, Field, inputClass, Modal, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { subTone } from "@/lib/admin";
import { api, fetchLanguages, fmtDate, type Language } from "@/lib/api";

type Row = { id: string; name: string; email: string; subscription_status: string; access_expires_at: string | null;
  language: string | null; is_active: boolean; manually_enrolled: boolean; created_at: string; last_login_at: string | null;
  dialogue_attempts: number; average_dialogue_score: number | null; last_attempt_at: string | null; flagged: boolean;
  teacher: { id: string; name: string } | null };

type NewStudent = { first_name: string; last_name: string; email: string; language: string; access: string; access_until: string;
  target_exam_date: string; note: string; signin: "invite" | "password"; password: string; teacher_id: string };

const EMPTY: NewStudent = { first_name: "", last_name: "", email: "", language: "", access: "Trial", access_until: "",
  target_exam_date: "", note: "", signin: "invite", password: "", teacher_id: "" };

type BulkResult = { report: ImportJob["report"]; committed: boolean; created: { id: string; email: string }[] };

export default function AdminStudents() {
  const router = useRouter();
  const { user } = useUser();
  const isAdmin = user.role === "admin";
  const teachers = useTeachers(isAdmin);
  const [teacher, setTeacher] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [bulk, setBulk] = useState(false);
  const [notice, setNotice] = useState("");
  const [languages, setLanguages] = useState<Language[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [emailing, setEmailing] = useState(false);

  const load = useCallback(() => api<Row[]>(`/admin/students?q=${encodeURIComponent(q)}&status=${status}&teacher=${teacher}`)
    .then(setRows).catch((e) => setError(e.message)), [q, status, teacher]);
  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);
  useEffect(() => { fetchLanguages().then(setLanguages).catch(() => {}); }, []);

  return (
    <>
      <PageHeader title={isAdmin ? "Students" : "My students"}
        subtitle={isAdmin ? "Profiles, access, attempts and scores. Add students by hand for demo accounts or offline payments."
          : "Students you enrolled or who joined through your class link. Students you add here are yours."}
        actions={<div className="flex gap-2">
          <Button variant="secondary" disabled={!selected.size} onClick={() => setEmailing(true)}>
            <Mail className="size-4" /> Email{selected.size ? ` ${selected.size}` : ""} selected</Button>
          <Button variant="secondary" onClick={() => setBulk(true)}><Upload className="size-4" /> Bulk enrol</Button>
          <Button onClick={() => setAdding(true)}><UserPlus className="size-4" /> Add student</Button>
        </div>} />
      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      <div className="mb-4 flex flex-wrap gap-3">
        <input placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} className={`${inputClass} mt-0 !w-72`} />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={`${inputClass} mt-0 !w-44`}>
          <option value="">Any access</option><option>Active</option><option>Trial</option><option>Expired</option><option>Inactive</option>
        </select>
        {isAdmin && <select value={teacher} onChange={(e) => setTeacher(e.target.value)} className={`${inputClass} mt-0 !w-52`} aria-label="Teacher">
          <option value="">Any teacher</option><option value="none">No teacher</option>
          {teachers.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.students})</option>)}
        </select>}
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      {!rows ? <Spinner /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr className="[&>th]:pr-4"><th className="w-10 pl-5"><input type="checkbox" aria-label="Select all shown" className="accent-brand-600"
                checked={rows.length > 0 && rows.every((r) => selected.has(r.id))}
                onChange={(e) => setSelected(e.target.checked ? new Set(rows.map((r) => r.id)) : new Set())} /></th>
                <th className="px-5 py-3">Student</th>{isAdmin && <th>Teacher</th>}<th>Language</th><th>Access</th><th>Attempts</th><th>Avg dialogue</th><th>Last attempt</th><th>Joined</th></tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} onClick={() => router.push(`/admin/students/${s.id}`)} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
                  <td className="pl-5" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" aria-label={`Select ${s.email}`} className="accent-brand-600" checked={selected.has(s.id)}
                      onChange={(e) => {
                        const next = new Set(selected);
                        if (e.target.checked) next.add(s.id); else next.delete(s.id);
                        setSelected(next);
                      }} /></td>
                  <td className="px-5 py-3"><Link href={`/admin/students/${s.id}`} className="font-medium hover:underline">{s.name}</Link>
                    <div className="text-xs text-slate-500">{s.email}
                      {s.flagged && <Badge tone="red" className="ml-2">Flagged</Badge>}
                      {!s.is_active && <Badge className="ml-2">Deactivated</Badge>}
                      {s.manually_enrolled && <Badge tone="violet" className="ml-2">Added by staff</Badge>}</div></td>
                  {isAdmin && <td>{s.teacher?.name ?? "–"}</td>}
                  <td>{s.language ?? "–"}</td>
                  <td><Badge tone={subTone(s.subscription_status)}>{s.subscription_status}</Badge>
                    {s.access_expires_at && <div className="mt-0.5 text-xs text-slate-500">until {fmtDate(s.access_expires_at)}</div>}</td>
                  <td className="tabular-nums">{s.dialogue_attempts}</td>
                  <td className="tabular-nums">{s.average_dialogue_score ?? "–"}</td>
                  <td>{s.last_attempt_at ? fmtDate(s.last_attempt_at) : "–"}</td>
                  <td>{fmtDate(s.created_at)}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={isAdmin ? 9 : 8} className="px-5 py-6 text-slate-500">
                {isAdmin || q || status ? "No students found." : "No students yet. Add them here, or share your class link from the Overview page."}</td></tr>}
            </tbody>
          </table>
        </Card>
      )}
      <AddStudent open={adding} languages={languages} teachers={teachers} onClose={() => setAdding(false)}
        onDone={(msg) => { setAdding(false); setNotice(msg); load(); }} />
      <MessageStudents open={emailing} recipients={(rows ?? []).filter((r) => selected.has(r.id))}
        onClose={() => setEmailing(false)} onSent={(msg) => { setEmailing(false); setSelected(new Set()); setNotice(msg); }} />
      <BulkEnrol open={bulk} teachers={teachers} onClose={() => { setBulk(false); load(); }} />
    </>
  );
}

function AddStudent({ open, languages, teachers, onClose, onDone }:
  { open: boolean; languages: Language[]; teachers: Teacher[]; onClose: () => void; onDone: (msg: string) => void }) {
  const [f, setF] = useState<NewStudent>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (patch: Partial<NewStudent>) => setF({ ...f, ...patch });

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/admin/students", { method: "POST", json: {
        first_name: f.first_name, last_name: f.last_name, email: f.email, language: f.language || null, access: f.access,
        access_until: f.access !== "None" && f.access_until ? f.access_until : null, target_exam_date: f.target_exam_date || null,
        note: f.note, send_invite: f.signin === "invite", password: f.signin === "password" ? f.password : null,
        teacher_id: f.teacher_id || null } });
      onDone(f.signin === "invite" ? `${f.email} added. An invite to set a password has been emailed.` : `${f.email} added. They can sign in with the password you set.`);
      setF(EMPTY);
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <Modal open={open} onClose={onClose} title="Add student">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name" value={f.first_name} onChange={(e) => set({ first_name: e.target.value })} />
          <Field label="Last name" value={f.last_name} onChange={(e) => set({ last_name: e.target.value })} />
        </div>
        <Field label="Email" type="email" value={f.email} onChange={(e) => set({ email: e.target.value })} />
        <label className="block"><span className="text-sm font-medium text-slate-700">Language</span>
          <select className={inputClass} value={f.language} onChange={(e) => set({ language: e.target.value })}>
            <option value="">Not set (student chooses)</option>
            {languages.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
          </select></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="text-sm font-medium text-slate-700">Access</span>
            <select className={inputClass} value={f.access} onChange={(e) => set({ access: e.target.value })}>
              <option value="Trial">Trial (full access)</option><option value="Active">Active (full access)</option><option value="None">None (free content only)</option>
            </select></label>
          <Field label="Access until" type="date" value={f.access_until} disabled={f.access === "None"}
            onChange={(e) => set({ access_until: e.target.value })} hint="Leave empty for no end date." />
        </div>
        <Field label="Target exam date (optional)" type="date" value={f.target_exam_date} onChange={(e) => set({ target_exam_date: e.target.value })} />
        {teachers.length > 0 && <TeacherSelect teachers={teachers} value={f.teacher_id} onChange={(id) => set({ teacher_id: id })} />}
        <Field label="Note (optional)" value={f.note} onChange={(e) => set({ note: e.target.value })} hint="E.g. demo account, paid by bank transfer." />
        <fieldset className="space-y-2 text-sm">
          <legend className="font-medium text-slate-700">How will they sign in?</legend>
          <label className="flex items-center gap-2"><input type="radio" className="accent-brand-600" checked={f.signin === "invite"} onChange={() => set({ signin: "invite" })} /> Email them a link to set their password</label>
          <label className="flex items-center gap-2"><input type="radio" className="accent-brand-600" checked={f.signin === "password"} onChange={() => set({ signin: "password" })} /> Set a password now (demo accounts; no email sent)</label>
        </fieldset>
        {f.signin === "password" && <Field label="Password" type="password" autoComplete="new-password" value={f.password} minLength={8}
          onChange={(e) => set({ password: e.target.value })} hint="At least 8 characters. Share it with the student yourself." />}
        {error && <ErrorNote>{error}</ErrorNote>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save} loading={busy}>Add student</Button></div>
      </div>
    </Modal>
  );
}

function BulkEnrol({ open, teachers, onClose }: { open: boolean; teachers: Teacher[]; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [teacherId, setTeacherId] = useState("");
  const [invites, setInvites] = useState(true);
  const [result, setResult] = useState<BulkResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async (commit: boolean) => {
    if (!file) return;
    setBusy(true);
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("commit", String(commit));
    fd.append("send_invites", String(invites));
    if (teacherId) fd.append("teacher_id", teacherId);
    try { setResult(await api<BulkResult>("/admin/students-import", { method: "POST", body: fd })); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  const close = () => { setFile(null); setResult(null); setError(""); onClose(); };

  return (
    <Modal open={open} onClose={close} title="Bulk enrol students" wide>
      <div className="space-y-4 text-sm">
        <p className="text-slate-600">Columns: <code>first_name, email</code> (required), <code>last_name, language, access, access_until, target_exam_date, note</code>.
          Access is Active, Trial or None; dates are YYYY-MM-DD or DD/MM/YYYY. Students who already have an account are skipped.</p>
        <CsvFormatButtons formatUrl="/api/admin/students-import/template" exampleUrl="/api/admin/students-import/example" />
        <input type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); }}
          className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200" />
        {teachers.length > 0 && <TeacherSelect teachers={teachers} value={teacherId} onChange={setTeacherId}
          label="Teacher for every student in the file" />}
        <label className="flex items-center gap-2 text-slate-600">
          <input type="checkbox" checked={invites} onChange={(e) => setInvites(e.target.checked)} className="accent-brand-600" />
          Email each new student a link to set their password
        </label>
        {!invites && <p className="text-xs text-amber-700">Without invites, set each student&apos;s password on their page before they can sign in.</p>}
        {result && <ImportReport job={{ id: "", type: "dialogues", file_name: file?.name ?? "students.csv",
          status: result.committed ? "Completed" : result.report.ok ? "Validated" : "Invalid", error: "", report: result.report,
          counts: result.committed ? { students_created: result.created.length } : {}, progress: {}, created_at: "", committed_at: null }} />}
        {error && <ErrorNote>{error}</ErrorNote>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>{result?.committed ? "Done" : "Cancel"}</Button>
          {!result?.committed && <Button variant="secondary" onClick={() => run(false)} loading={busy && !result} disabled={!file}>Check file</Button>}
          {result && !result.committed && <Button onClick={() => run(true)} loading={busy} disabled={!result.report.ok || !result.report.summary.to_create}>
            Enrol {result.report.summary.to_create} student{result.report.summary.to_create === 1 ? "" : "s"}</Button>}
        </div>
      </div>
    </Modal>
  );
}
