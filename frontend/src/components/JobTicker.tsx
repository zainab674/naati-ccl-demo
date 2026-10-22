"use client";

/**
 * On hosts without a background worker (Vercel), queued jobs (scoring, audio processing) run when the site asks:
 * while anything is waiting, this calls POST /api/jobs/tick every few seconds. Off unless NEXT_PUBLIC_JOB_TICKER=1.
 */
import { useEffect } from "react";

import { api } from "@/lib/api";

const ON = process.env.NEXT_PUBLIC_JOB_TICKER === "1";

export function JobTicker() {
  useEffect(() => {
    if (!ON) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      let pending = 0;
      try {
        pending = (await api<{ ran: number; pending: number }>("/jobs/tick", { method: "POST" })).pending;
      } catch { /* signed out or offline: try again later */ }
      if (!stop) timer = setTimeout(tick, pending > 0 ? 2000 : 20000);
    };
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, []);
  return null;
}
