"use client";

import { UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Badge, Button, Card, ErrorNote, Field, inputClass, Modal, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";

type Member = { id: string; name: string; email: string; role: "admin" | "teacher"; is_active: boolean;
  last_login_at: string | null; created_at: string };

const ROLE_HELP = {
  teacher: "Students, enrolment and attempt review. Cannot edit content, import CSVs, change settings or manage the team.",
  admin: "Everything, including content, imports, settings and the team.",
};

export default function AdminTeam() {
  const { user } = useUser();
  const [rows, setRows] = useState<Member[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => api<Member[]>("/admin/team").then(setRows).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const update = async (m: Member, json: Partial<Pick<Member, "is_active">> & { role?: string }, msg: string) => {
    setError("");
    try { await api(`/admin/team/${m.id}`, { method: "PATCH", json }); setNotice(msg); load(); }
    catch (e) { setError((e as Error).message); }
  };

  return (
    <>
      <PageHeader title="Team" subtitle="Admins and teachers who can sign in to the staff area."
        actions={<Button onClick={() => setAdding(true)}><UserPlus className="size-4" /> Add team member</Button>} />
      {notice && <div className="mb-4"><SuccessNote>{notice}</SuccessNote></div>}
      {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}
      {!rows ? <Spinner /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
              <tr className="[&>th]:pr-4"><th className="px-5 py-3">Name</th><th>Role</th><th>Last sign-in</th><th>Added</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((m) => {
                const self = m.id === user.id;
                return (
                  <tr key={m.id} className="border-t border-slate-100">
                    <td className="px-5 py-3"><div className="font-medium">{m.name}{self && <span className="text-slate-400"> (you)</span>}</div>
                      <div className="text-xs text-slate-500">{m.email}{!m.is_active && <Badge className="ml-2">Deactivated</Badge>}</div></td>
                    <td>
                      <select className={`${inputClass} mt-0 !w-32`} value={m.role} disabled={self}
                        onChange={(e) => update(m, { role: e.target.value }, `${m.email} is now ${e.target.value === "admin" ? "an admin" : "a teacher"}.`)}>
                        <option value="teacher">Teacher</option><option value="admin">Admin</option>
                      </select>
                    </td>
                    <td>{m.last_login_at ? fmtDate(m.last_login_at) : "Never"}</td>
                    <td>{fmtDate(m.created_at)}</td>
                    <td className="pr-5 text-right">
                      {!self && <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" onClick={() => update(m, { is_active: !m.is_active },
                          m.is_active ? `${m.email} is deactivated and signed out.` : `${m.email} can sign in again.`)}>
                          {m.is_active ? "Deactivate" : "Reactivate"}</Button>
                        <Button size="sm" variant="ghost" onClick={() => {
                          if (confirm(`Remove ${m.email} from the team? Their account stays, as a student account.`))
                            update(m, { role: "student" }, `${m.email} was removed from the team.`);
                        }}>Remove</Button>
                      </div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
      <AddMember open={adding} onClose={() => setAdding(false)}
        onDone={(msg) => { setAdding(false); setNotice(msg); load(); }} />
    </>
  );
}

function AddMember({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (msg: string) => void }) {
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", role: "teacher" as "teacher" | "admin" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await api<{ email: string; invited: boolean }>("/admin/team", { method: "POST", json: f });
      onDone(r.invited ? `${r.email} added. An invite to set a password has been emailed.`
        : `${r.email} already had an account and is now on the team.`);
      setF({ first_name: "", last_name: "", email: "", role: "teacher" });
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <Modal open={open} onClose={onClose} title="Add team member">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name" value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} />
          <Field label="Last name" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} />
        </div>
        <Field label="Email" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })}
          hint="If this person already has a student account, it becomes a team account (no invite is sent)." />
        <label className="block"><span className="text-sm font-medium text-slate-700">Role</span>
          <select className={inputClass} value={f.role} onChange={(e) => setF({ ...f, role: e.target.value as "teacher" | "admin" })}>
            <option value="teacher">Teacher</option><option value="admin">Admin</option>
          </select>
          <span className="mt-1 block text-xs text-slate-500">{ROLE_HELP[f.role]}</span></label>
        {error && <ErrorNote>{error}</ErrorNote>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save} loading={busy}>Add</Button></div>
      </div>
    </Modal>
  );
}
