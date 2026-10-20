"use client";

/**
 * Exam chrome for the test player, laid out like the NAATI CCL online test (assessmentQ): a header with the user,
 * a breadcrumb bar with the page counter, a page title bar with Help, the page body, and a footer with a progress
 * strip and Previous / Next. Our own branding only; nothing here uses NAATI's name or logo.
 */
import { ArrowLeft, ArrowRight, CameraOff, CircleHelp, Volume2 } from "lucide-react";
import { type ReactNode, type RefObject, useEffect, useRef } from "react";

import { Logo } from "./Logo";
import { cx } from "./ui";

export type FooterCell = { state: "done" | "current" | "todo" | "skipped" };

export function ExamFrame({ user, crumb, pageNo, pageCount, title, onHelp, cells, onPrev, onNext, prevDisabled, nextDisabled, nextLabel, children }: {
  user: { name: string; email: string } | null; crumb: string; pageNo: number; pageCount: number; title: string;
  onHelp: () => void; cells: FooterCell[]; onPrev?: () => void; onNext?: () => void; prevDisabled?: boolean;
  nextDisabled?: boolean; nextLabel?: string; children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-white text-[15px] text-slate-800" onContextMenu={(e) => e.preventDefault()}>
      <header className="flex h-14 items-center justify-between border-b-2 border-brand-600 px-4 sm:px-6">
        <Logo compact />
        {user && <div className="text-right text-sm leading-tight"><div className="font-medium">{user.name}</div><div className="text-xs text-slate-500">{user.email}</div></div>}
      </header>
      <div className="flex h-9 items-center justify-between border-b border-slate-200 bg-slate-50 px-4 text-xs text-slate-600 sm:px-6">
        <div className="flex min-w-0 items-center gap-2"><span className="truncate">{crumb}</span></div>
        <div className="flex items-center gap-2 tabular-nums">
          <span>{pageNo}/{pageCount}</span>
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-emerald-600" style={{ width: `${(100 * pageNo) / pageCount}%` }} /></div>
        </div>
      </div>
      <div className="flex h-11 items-center justify-between border-b border-slate-200 px-4 sm:px-6">
        <h1 className="text-sm font-semibold">{title}</h1>
        <button onClick={onHelp} className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-ink"><CircleHelp className="size-4" /> Help</button>
      </div>
      <main className="flex-1 px-4 py-6 sm:px-6">{children}</main>
      <footer className="sticky bottom-0 border-t border-slate-200 bg-white">
        <div className="flex gap-0.5 px-4 pt-2 sm:px-6" aria-label="Test progress">
          {cells.map((c, i) => (
            <div key={i} className={cx("h-1.5 flex-1 rounded-sm",
              c.state === "current" ? "bg-emerald-700" : c.state === "done" ? "bg-emerald-400" : c.state === "skipped" ? "bg-rose-300" : "bg-slate-200")} />
          ))}
        </div>
        <div className="flex items-center justify-end gap-3 px-4 py-3 sm:px-6">
          <button onClick={onPrev} disabled={prevDisabled || !onPrev}
            className="inline-flex h-9 items-center gap-1.5 rounded-full px-4 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-40">
            <ArrowLeft className="size-4" /> Previous</button>
          <button onClick={onNext} disabled={nextDisabled || !onNext}
            className="inline-flex h-9 items-center gap-1.5 rounded-full bg-emerald-700 px-5 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-40">
            {nextLabel ?? "Next"} <ArrowRight className="size-4" /></button>
        </div>
      </footer>
    </div>
  );
}

/** The look of a button, used inside instructions ("Click [Start] and speak after the chime"). */
export function InlineBtn({ children, outline }: { children: ReactNode; outline?: boolean }) {
  return <span className={cx("mx-1 inline-flex h-7 items-center rounded-full px-3 text-xs font-medium",
    outline ? "border border-slate-400 text-slate-700" : "bg-emerald-700 text-white")}>{children}</span>;
}

export function StartButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled}
    className="inline-flex h-9 items-center rounded-full bg-emerald-700 px-6 text-sm font-medium text-white hover:bg-emerald-800 disabled:bg-slate-300">Start</button>;
}

export function FinishButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled}
    className="inline-flex h-9 items-center rounded-full border border-slate-500 px-4 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:border-slate-200 disabled:text-slate-300">Finish attempt</button>;
}

export function RecBadge() {
  return <span className="inline-flex h-7 items-center gap-1.5 rounded border border-rose-300 bg-rose-50 px-2 text-xs font-semibold text-rose-600">
    <span className="size-2 animate-pulse rounded-full bg-rose-600" /> REC</span>;
}

/** Live camera preview. The stream is only shown, never recorded or uploaded. */
export function WebcamBox({ stream, recording }: { stream: MediaStream | null; recording: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);
  const hasVideo = !!stream?.getVideoTracks().length;
  useEffect(() => {
    if (ref.current) ref.current.srcObject = hasVideo ? stream : null;
  }, [stream, hasVideo]);
  return (
    <div className={cx("mx-auto flex aspect-[4/3] w-full max-w-64 items-center justify-center overflow-hidden rounded bg-slate-100 ring-2",
      recording ? "ring-rose-500" : "ring-transparent")}>
      {hasVideo
        ? <video ref={ref} autoPlay muted playsInline className="size-full -scale-x-100 object-cover" />
        : <div className="flex flex-col items-center gap-1 text-xs text-slate-400"><CameraOff className="size-6" /> Camera off</div>}
    </div>
  );
}

/** Source audio row: the segment's waveform image with a moving playhead. */
export function SourceWave({ src, progress }: { src: string | null; progress: number }) {
  return (
    <div className="flex items-center gap-2">
      <Volume2 className="size-4 shrink-0 text-slate-500" />
      <div className="relative h-14 flex-1 overflow-hidden rounded-sm bg-slate-100">
        {/* eslint-disable-next-line @next/next/no-img-element -- protected image from the API, not next/image */}
        {src && <img src={src} alt="" draggable={false} className="size-full object-fill opacity-70 grayscale" />}
        {!src && <div className="absolute inset-x-0 top-1/2 h-px bg-slate-300" />}
        <div className="absolute inset-y-0 left-0 w-0.5 bg-emerald-600" />
        {progress > 0 && <div className="absolute inset-y-0 w-0.5 bg-rose-500" style={{ left: `${Math.min(100, progress * 100)}%` }} />}
      </div>
    </div>
  );
}

/**
 * Recording row: a live trace of the microphone level, drawn from samplesRef (0..1, one every ~50 ms) across the
 * response window. Shaded red while recording; after Finish attempt it keeps showing the recorded trace.
 */
export function MicWave({ samplesRef, capacity, recording, tick }: {
  samplesRef: RefObject<number[]>; capacity: number; recording: boolean; tick: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const w = (c.width = c.clientWidth * devicePixelRatio);
    const h = (c.height = c.clientHeight * devicePixelRatio);
    const g = c.getContext("2d")!;
    g.clearRect(0, 0, w, h);
    const s = samplesRef.current ?? [];
    const filled = Math.min(1, s.length / capacity);
    if (recording || s.length) {
      g.fillStyle = recording ? "rgba(244,63,94,0.12)" : "rgba(16,185,129,0.08)";
      g.fillRect(0, 0, w * filled, h);
    }
    g.strokeStyle = recording ? "#e11d48" : "#047857";
    g.lineWidth = devicePixelRatio;
    g.beginPath();
    const step = w / capacity;
    s.slice(-capacity).forEach((v, i) => {
      const amp = Math.max(0.02, v) * h * 0.45;
      g.moveTo(i * step, h / 2 - amp);
      g.lineTo(i * step, h / 2 + amp);
    });
    g.stroke();
    g.strokeStyle = "#cbd5e1";
    g.beginPath();
    g.moveTo(w * filled, h / 2);
    g.lineTo(w, h / 2);
    g.stroke();
  }, [samplesRef, capacity, recording, tick]);
  return <div className="ml-6 h-14 overflow-hidden rounded-sm bg-slate-50"><canvas ref={canvas} className="size-full" /></div>;
}

export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
