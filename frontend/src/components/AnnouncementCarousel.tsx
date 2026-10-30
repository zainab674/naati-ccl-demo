"use client";

import { CalendarClock, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { fmtDateTime } from "@/lib/api";
import { cx } from "./ui";

export type Announcement = {
  id: string; kind: string; kind_label: string; title: string; body: string; event_at: string | null;
  link_url: string; link_label: string; language_name: string | null;
};

const ROTATE_MS = 7000;

/** Dashboard carousel: live sessions, 1-on-1 classes and news. Rotates until the student interacts with it. */
export default function AnnouncementCarousel({ items }: { items: Announcement[] }) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const n = items.length;
  useEffect(() => {
    if (n < 2 || paused) return;
    const t = setInterval(() => setI((x) => (x + 1) % n), ROTATE_MS);
    return () => clearInterval(t);
  }, [n, paused]);
  if (!n) return null;
  const a = items[Math.min(i, n - 1)];
  const go = (to: number) => { setPaused(true); setI((to + n) % n); };
  const external = a.link_url.startsWith("http");

  return (
    <section aria-roledescription="carousel" aria-label="Announcements" className="mb-6 overflow-hidden rounded-xl bg-brand-900 text-white shadow-sm"
      onMouseEnter={() => setPaused(true)} onFocus={() => setPaused(true)}>
      <div className="flex items-stretch">
        {n > 1 && <button onClick={() => go(i - 1)} aria-label="Previous announcement" className="px-2 text-brand-200 hover:bg-white/5 hover:text-white sm:px-3">
          <ChevronLeft className="size-5" /></button>}
        <div className="min-w-0 flex-1 px-3 py-5 sm:px-4" aria-live={paused ? "polite" : "off"}>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-white/15 px-2 py-0.5 font-medium">{a.kind_label}</span>
            {a.language_name && <span className="text-brand-200">{a.language_name}</span>}
            {a.event_at && <span className="inline-flex items-center gap-1 text-brand-100"><CalendarClock className="size-3.5" /> {fmtDateTime(a.event_at)}</span>}
          </div>
          <h2 className="mt-2 text-lg font-semibold">{a.title}</h2>
          {a.body && <p className="mt-1 whitespace-pre-line text-sm text-brand-100">{a.body}</p>}
          {a.link_url && (external
            ? <a href={a.link_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-brand-900 hover:bg-brand-50">
                {a.link_label || "Open"} <ExternalLink className="size-3.5" /></a>
            : <Link href={a.link_url} className="mt-3 inline-flex items-center rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-brand-900 hover:bg-brand-50">
                {a.link_label || "Open"}</Link>)}
        </div>
        {n > 1 && <button onClick={() => go(i + 1)} aria-label="Next announcement" className="px-2 text-brand-200 hover:bg-white/5 hover:text-white sm:px-3">
          <ChevronRight className="size-5" /></button>}
      </div>
      {n > 1 && (
        <div className="flex justify-center gap-1.5 pb-3">
          {items.map((x, k) => (
            <button key={x.id} onClick={() => go(k)} aria-label={`Announcement ${k + 1} of ${n}`} aria-current={k === i}
              className={cx("h-1.5 rounded-full transition-all", k === i ? "w-5 bg-white" : "w-1.5 bg-white/40 hover:bg-white/70")} />
          ))}
        </div>
      )}
    </section>
  );
}
