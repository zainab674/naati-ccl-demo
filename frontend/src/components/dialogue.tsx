"use client";

import { Flag, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api, type Activity } from "@/lib/api";
import { Button, DifficultyBadge, ErrorNote, Modal } from "./ui";

export function useStartAttempt() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const start = async (body: { mode: "practice" | "mock"; activity_id?: string; mock_test_id?: string }) => {
    setBusy(body.activity_id ?? body.mock_test_id ?? "x");
    try {
      const r = await api<{ id: string }>("/attempts", { method: "POST", json: body });
      router.push(`/attempt/${r.id}`);
    } catch (e) {
      alert((e as Error).message);
      setBusy(null);
    }
  };
  return { start, busy };
}

export function ReportButton({ activity }: { activity: Pick<Activity, "id" | "title"> }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | string>("idle");
  const send = async () => {
    setState("sending");
    try {
      await api(`/activities/${activity.id}/report`, { method: "POST", json: { text } });
      setState("sent");
    } catch (e) {
      setState((e as Error).message);
    }
  };
  return (
    <>
      <button onClick={() => { setOpen(true); setState("idle"); setText(""); }}
        className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700">
        <Flag className="size-3.5" /> Report
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Report an issue">
        {state === "sent" ? (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">Thanks. The content team will review <b>{activity.title}</b>.</p>
            <Button onClick={() => setOpen(false)}>Close</Button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">What&apos;s wrong with <b>{activity.title}</b>? Audio quality, a wrong reference, a typo…</p>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4}
              className="w-full rounded-lg border border-slate-300 p-3 text-sm outline-none focus:border-brand-500"
              placeholder="e.g. Segment 4 cuts off before the speaker finishes" />
            {state !== "idle" && state !== "sending" && <ErrorNote>{state}</ErrorNote>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={send} disabled={text.trim().length < 3} loading={state === "sending"}>Send report</Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

export function DialogueTable({ items, compact }: { items: Activity[]; compact?: boolean }) {
  const { start, busy } = useStartAttempt();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <th className="w-12 py-3 pl-5 pr-2">#</th>
            <th className="py-3 pr-4">Title / scenario</th>
            <th className="py-3 pr-4">Domain</th>
            <th className="py-3 pr-4">Difficulty</th>
            {!compact && <th className="py-3 pr-4">Length</th>}
            <th className="py-3 pr-5 text-right"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((a) => (
            <tr key={a.id} className="group hover:bg-slate-50/60">
              <td className="py-4 pl-5 pr-2 align-top tabular-nums text-slate-400">{a.number}</td>
              <td className="py-4 pr-4 align-top">
                <div className="font-medium text-ink">{a.title}
                  {a.practiced && <span className="ml-2 text-xs font-normal text-emerald-600">✓ practised</span>}
                </div>
                <div className="mt-0.5 max-w-xl text-slate-500">{a.scenario}</div>
              </td>
              <td className="py-4 pr-4 align-top text-slate-600">{a.domain}</td>
              <td className="py-4 pr-4 align-top"><DifficultyBadge level={a.difficulty} /></td>
              {!compact && <td className="py-4 pr-4 align-top text-slate-500">{a.segment_count} segments</td>}
              <td className="py-4 pr-5 align-top">
                <div className="flex items-center justify-end gap-1">
                  <ReportButton activity={a} />
                  <Button size="sm" variant="secondary" loading={busy === a.id}
                    onClick={() => start({ mode: "practice", activity_id: a.id })}>
                    <Play className="size-3.5" /> Practise
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
