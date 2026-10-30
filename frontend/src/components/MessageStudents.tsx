"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { Button, ErrorNote, Field, inputClass, Modal } from "./ui";

/** Email one or many students. {first_name} and {name} are filled in per student by the server. */
export default function MessageStudents({ open, recipients, onClose, onSent }: {
  open: boolean; recipients: { id: string; email: string }[]; onClose: () => void; onSent: (msg: string) => void;
}) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("Hi {first_name},\n\n");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const send = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await api<{ queued: number; skipped: number }>("/admin/students/message", {
        method: "POST", json: { user_ids: recipients.map((x) => x.id), subject, body } });
      onSent(`Email sent to ${r.queued} student${r.queued === 1 ? "" : "s"}`
        + (r.skipped ? ` (${r.skipped} deactivated account${r.skipped === 1 ? "" : "s"} skipped).` : "."));
      setSubject("");
      setBody("Hi {first_name},\n\n");
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  const to = recipients.length === 1 ? recipients[0].email : `${recipients.length} students`;
  return (
    <Modal open={open} onClose={onClose} title={`Email ${to}`} wide>
      <div className="space-y-4">
        <Field label="Subject" value={subject} maxLength={200} onChange={(e) => setSubject(e.target.value)} />
        <label className="block"><span className="text-sm font-medium text-slate-700">Message</span>
          <textarea className={`${inputClass} min-h-48`} value={body} maxLength={10000} onChange={(e) => setBody(e.target.value)} />
          <span className="mt-1 block text-xs text-slate-500">Plain text. <code>{"{first_name}"}</code> and <code>{"{name}"}</code> are
            replaced with each student&apos;s name. Your name is added at the end. For account and course messages, not marketing.</span>
        </label>
        {error && <ErrorNote>{error}</ErrorNote>}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={send} loading={busy} disabled={!subject.trim() || !body.trim()}>Send email</Button>
        </div>
      </div>
    </Modal>
  );
}
