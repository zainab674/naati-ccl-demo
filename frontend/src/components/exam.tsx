"use client";

/**
 * Exam chrome for the test player, laid out like the NAATI CCL online test (assessmentQ): a white header with the
 * user at the top right over a thick teal line, a breadcrumb bar with the page counter, progress bar and countdown,
 * a page title bar with Help, the page body, and a footer with a segmented progress strip and Previous / Next.
 * Our own logo and name only; nothing here uses NAATI's name or logo.
 */
import { ArrowLeft, ArrowRight, CameraOff, ChevronDown, CircleHelp, Flag, Info, Play, Square, Timer, VideoOff, Volume2, X } from "lucide-react";
import Link from "next/link";
import { type ReactNode, type RefObject, useEffect, useRef, useState } from "react";

import { Logo } from "./Logo";
import { BrandName } from "./Theme";
import { cx } from "./ui";

/** Exam colours (the online test's look), kept in one place. */
export const EXAM = {
  accent: "#008d7f",      // header line, buttons
  accentDark: "#00756a",
  heading: "#1abc9c",     // page headings
  text: "#282c2e",
  muted: "#535658",
  finish: "#c8102e",      // Finish button on the last page
  strip: "#86b5af",       // visited cells of the progress strip
};

export type FooterCell = { state: "done" | "current" | "todo" };

export function ExamFrame({ user, crumb, pageNo, pageCount, timer, title, onHelp, cells, onPrev, onNext, prevDisabled, nextDisabled, finish, children }: {
  user: { name: string; email: string } | null; crumb: string; pageNo: number; pageCount: number; timer: ReactNode;
  title: string; onHelp: () => void; cells: FooterCell[]; onPrev?: () => void; onNext?: () => void; prevDisabled?: boolean;
  nextDisabled?: boolean; finish?: { onClick: () => void; disabled?: boolean }; children: ReactNode;
}) {
  const [menu, setMenu] = useState(false);
  return (
    <div className="exam flex h-screen flex-col bg-white text-[14px]" style={{ color: EXAM.text }} onContextMenu={(e) => e.preventDefault()}>
      <header className="flex h-[70px] shrink-0 items-center justify-between bg-white px-5" style={{ borderBottom: `4px solid ${EXAM.accent}` }}>
        <Logo compact />
        {user && (
          <div className="relative flex items-center gap-3">
            <div className="text-right leading-tight">
              <div className="text-[15px] font-semibold" style={{ color: "#4c4d4f" }}>{user.name}<span className="hidden md:inline"> ({user.email})</span></div>
              <div className="text-[12px]" style={{ color: EXAM.muted }}><BrandName /></div>
            </div>
            <button onClick={() => setMenu((m) => !m)} aria-label="Account menu" aria-expanded={menu}
              className="flex size-5 items-center justify-center rounded-full text-white" style={{ background: "#3c3d3f" }}>
              <ChevronDown className="size-3.5" strokeWidth={3} />
            </button>
            {menu && (
              <div className="absolute right-0 top-9 z-30 w-48 rounded border border-slate-200 bg-white py-1 text-[13px] shadow-lg">
                <Link href="/dashboard" className="block px-4 py-2 hover:bg-slate-50">Leave the test</Link>
                <p className="px-4 pb-2 text-[11px] text-slate-500">Your answers are saved. Open the test again to continue.</p>
              </div>
            )}
          </div>
        )}
      </header>
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-[#e3e4e4] px-2.5 text-[13px]">
        <div className="flex min-w-0 items-center gap-2">
          <span className="max-w-[16ch] truncate">{crumb}</span><span className="text-slate-400">/</span><span>Dialogue</span>
        </div>
        <div className="flex items-center gap-10">
          <div className="hidden items-center gap-2 font-semibold tabular-nums sm:flex" style={{ color: EXAM.muted }}>
            <span>{pageNo}/{pageCount}</span>
            <div className="h-2.5 w-[120px] overflow-hidden rounded-full border border-[#c9cccc] bg-white">
              <div className="h-full rounded-full" style={{ width: `${(100 * pageNo) / pageCount}%`, background: EXAM.strip }} />
            </div>
          </div>
          <div className="flex items-center gap-1.5 font-semibold tabular-nums"><Timer className="size-4" /> {timer}</div>
        </div>
      </div>
      <div className="flex h-[50px] shrink-0 items-center justify-between border-b border-[#e3e4e4] px-4 sm:px-10">
        <h1 className="text-[15px] font-semibold">{title}</h1>
        <button onClick={onHelp} className="inline-flex items-center gap-2 text-[13px] font-semibold hover:underline"><CircleHelp className="size-4" /> Help</button>
      </div>
      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-7 sm:px-10">{children}</main>
      <footer className="shrink-0 bg-white">
        <div className="flex gap-0.5" aria-label="Test progress">
          {cells.map((c, i) => (
            <div key={i} className="h-2 flex-1" style={{ background: c.state === "todo" ? "#eceeee" : c.state === "current" ? EXAM.accent : EXAM.strip }} />
          ))}
        </div>
        <div className="flex h-[60px] items-center justify-end gap-6 border-t border-[#e3e4e4] px-4 sm:px-10">
          <button onClick={onPrev} disabled={prevDisabled || !onPrev}
            className="inline-flex items-center gap-3 text-[13px] font-semibold disabled:text-[#d4d5d5]">
            <ArrowLeft className="size-4" /> Previous</button>
          {finish
            ? <button onClick={finish.onClick} disabled={finish.disabled}
                className="inline-flex h-10 items-center gap-3 rounded-[20px] px-6 text-[13px] font-semibold text-white disabled:opacity-50" style={{ background: EXAM.finish }}>
                <Flag className="size-4 fill-white" /> Finish</button>
            : <button onClick={onNext} disabled={nextDisabled || !onNext}
                className="inline-flex h-10 w-28 items-center justify-center gap-3 rounded-[20px] text-[13px] font-semibold text-white disabled:opacity-40" style={{ background: EXAM.accent }}>
                Next <ArrowRight className="size-4" /></button>}
        </div>
      </footer>
    </div>
  );
}

/** Page heading in the test's teal ("INFORMATION FOR CANDIDATES", "Filipino CCL test"). */
export function ExamHeading({ children, upper }: { children: ReactNode; upper?: boolean }) {
  return <h2 className={cx("font-bold", upper ? "text-[16px] uppercase" : "text-[18px]")} style={{ color: EXAM.heading }}>{children}</h2>;
}

/** The look of a button, used inside instructions ("Click [Start] and speak after the chime"). */
export function InlineBtn({ children, outline }: { children: ReactNode; outline?: boolean }) {
  return <span className={cx("mx-2 inline-flex h-[50px] items-center justify-center rounded-[25px] px-7 align-middle text-[15px] font-semibold",
    outline ? "border border-[#3c3d3f] bg-white" : "text-white")} style={outline ? undefined : { background: EXAM.accent }}>{children}</span>;
}

/** Small round Next icon, as in "Please click Next (→) to start". */
export function InlineNext() {
  return <span className="mx-1 inline-flex size-7 items-center justify-center rounded-full border align-middle" style={{ borderColor: EXAM.accent, color: EXAM.accent }}><ArrowRight className="size-3.5" /></span>;
}

/** Small red Finish pill, as in "Please click on [Finish] at the bottom of the screen". */
export function InlineFinish() {
  return <span className="mx-1 inline-flex h-6 items-center gap-1.5 rounded-full border px-4 align-middle text-[10px]" style={{ borderColor: EXAM.finish, color: EXAM.finish }}><Flag className="size-3" style={{ fill: EXAM.finish }} /> Finish</span>;
}

export function StartButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled}
    className="inline-flex h-10 min-w-[90px] items-center justify-center rounded-[20px] border px-5 text-[13px] font-semibold text-white disabled:border-[#d4d5d5] disabled:!bg-white disabled:text-[#c3c5c5]"
    style={{ background: EXAM.accent, borderColor: EXAM.accent }}>Start</button>;
}

export function FinishButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled}
    className="inline-flex h-10 items-center rounded-[20px] border border-[#3c3d3f] bg-white px-5 text-[13px] font-semibold hover:bg-slate-50 disabled:border-[#d4d5d5] disabled:text-[#c3c5c5]">Finish attempt</button>;
}

/** Round outline icon button (Play / Stop on the example segment). */
export function RoundBtn({ onClick, disabled, label, children }: { onClick: () => void; disabled?: boolean; label: string; children: ReactNode }) {
  return <button onClick={onClick} disabled={disabled} aria-label={label} title={label}
    className="inline-flex size-10 items-center justify-center rounded-full border border-[#9a9c9d] text-[#3c3d3f] hover:bg-slate-50 disabled:border-[#e0e1e1] disabled:text-[#c3c5c5]">{children}</button>;
}
export const PlayIcon = () => <Play className="size-3.5 fill-current" />;
export const StopIcon = () => <Square className="size-3 fill-current" />;

/** Live camera preview. The stream is only shown, never recorded or uploaded. */
export function WebcamBox({ stream, recording, issue, onRetry, onTurnOff }: {
  stream: MediaStream | null; recording: boolean; issue?: string; onRetry?: () => void; onTurnOff?: () => void;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const hasVideo = !!stream?.getVideoTracks().length;
  useEffect(() => {
    if (ref.current) ref.current.srcObject = hasVideo ? stream : null;
  }, [stream, hasVideo]);
  return (
    <div className={cx("relative mx-auto flex aspect-[4/3] w-full max-w-[320px] items-center justify-center overflow-hidden rounded border-2 bg-[#f2f2f2]",
      recording ? "border-rose-500" : "border-[#d4d5d5]")}>
      {hasVideo
        ? <>
            <video ref={ref} autoPlay muted playsInline className="size-full -scale-x-100 object-cover" />
            {onTurnOff && (
              <button onClick={onTurnOff} aria-label="Turn camera off" title="Turn camera off"
                className="absolute bottom-2 right-2 flex size-8 items-center justify-center rounded-full bg-black/55 text-white hover:bg-black/75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
                <VideoOff className="size-4" />
              </button>
            )}
          </>
        : (issue || onRetry) && <div className="flex flex-col items-center gap-1.5 px-4 text-center text-[12px] text-slate-500">
            <CameraOff className="size-6 text-slate-400" /> <span className="font-semibold">Camera off</span>
            {issue && <span className="leading-snug">{issue}</span>}
            {onRetry && !recording && <button onClick={onRetry} className="mt-1 rounded-full bg-white px-3 py-1 font-semibold ring-1 ring-slate-300 hover:bg-slate-50">Turn camera on</button>}
          </div>}
    </div>
  );
}

/**
 * Source audio row: speaker icon over a vertical volume slider, then the segment's waveform image with the red end
 * marker and a moving playhead.
 */
export function SourceWave({ src, progress, volume, onVolume }: { src: string | null; progress: number; volume: number; onVolume: (v: number) => void }) {
  return (
    <div>
      <Volume2 className="mb-1 ml-[5px] size-4" />
      <div className="flex h-16 items-stretch">
        <div className="flex w-6 shrink-0 justify-center bg-[#f2f2f2] py-1.5">
          <input type="range" min={0} max={1} step={0.05} value={volume} onChange={(e) => onVolume(Number(e.target.value))}
            aria-label="Volume" className="exam-volume h-full" style={{ writingMode: "vertical-lr", direction: "rtl", accentColor: EXAM.accent }} />
        </div>
        <div className="relative flex-1 overflow-hidden bg-[#f2f2f2]">
          {/* eslint-disable-next-line @next/next/no-img-element -- protected image from the API, not next/image */}
          {src && <img src={src} alt="" draggable={false} className="size-full object-fill opacity-40 grayscale" />}
          {!src && <div className="absolute inset-x-0 top-1/2 h-px bg-[#c3c5c5]" />}
          <div className="absolute inset-y-0 left-0 w-0.5 bg-[#3c3d3f]" />
          <div className="absolute inset-y-0 right-0 w-px bg-[#f36b7f]" />
          <div className="absolute right-0 top-0 h-4 w-2.5 rounded-b-sm bg-[#f36b7f]" />
          {progress > 0 && <div className="absolute inset-y-0 w-0.5" style={{ left: `${Math.min(100, progress * 100)}%`, background: EXAM.accent }} />}
        </div>
      </div>
    </div>
  );
}

/**
 * Recording row: a live trace of the microphone level, drawn from samplesRef (0..1, one every ~50 ms) across the
 * response window, on the light-grey track.
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
    g.strokeStyle = recording ? EXAM.accent : "#9a9c9d";
    g.lineWidth = devicePixelRatio * 1.5;
    g.beginPath();
    const step = w / capacity;
    s.slice(-capacity).forEach((v, i) => {
      const amp = Math.max(0.01, v) * h * 0.45;
      g.moveTo(i * step, h / 2 - amp);
      g.lineTo(i * step, h / 2 + amp);
    });
    g.stroke();
  }, [samplesRef, capacity, recording, tick]);
  return <div className="ml-6 h-16 overflow-hidden bg-[#ececec]"><canvas ref={canvas} className="size-full" /></div>;
}

/** Popup in the online test's style: title with a close cross, body, buttons at the bottom right. */
export function ExamModal({ open, onClose, title, children, actions, wide }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; actions?: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 p-4" style={{ color: EXAM.text }} onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" onMouseDown={(e) => e.stopPropagation()}
        className={cx("w-full rounded-sm bg-white shadow-xl", wide ? "max-w-[454px]" : "max-w-[450px]")}>
        {typeof title === "string"
          ? <div className="flex items-center justify-between border-b border-[#e3e4e4] px-5 py-3">
              <h2 className="text-[22px] font-light">{title}</h2>
              <button onClick={onClose} aria-label="Close" className="text-[#3c3d3f] hover:text-black"><X className="size-4" strokeWidth={3} /></button>
            </div>
          : title}
        <div className="px-5 py-5 text-[13px] leading-relaxed">{children}</div>
        {actions && <div className="flex items-center justify-end gap-6 border-t border-[#e3e4e4] px-5 py-4">{actions}</div>}
      </div>
    </div>
  );
}

/** Teal pill (OK / Close in popups). */
export function ExamPill({ onClick, children, disabled }: { onClick: () => void; children: ReactNode; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled} className="inline-flex h-[30px] min-w-[90px] items-center justify-center rounded-[15px] px-5 text-[13px] font-semibold text-white disabled:opacity-50"
    style={{ background: EXAM.accent }}>{children}</button>;
}
export function ExamTextBtn({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return <button onClick={onClick} className="text-[13px] font-semibold hover:underline">{children}</button>;
}

/** Status icon for a row of the End of dialogue list. */
export function RowIcon({ info }: { info?: boolean }) {
  return info
    ? <span className="flex size-[18px] items-center justify-center rounded-full bg-[#535658] text-white"><Info className="size-3" strokeWidth={3} /></span>
    : <span className="flex size-[18px] items-center justify-center rounded-full border-2 border-[#535658]"><span className="size-1.5 rounded-full bg-[#535658]" /></span>;
}

export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
export const hhmmss = (s: number) => {
  const t = Math.max(0, Math.floor(s));
  return [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60].map((n) => String(n).padStart(2, "0")).join(":");
};
