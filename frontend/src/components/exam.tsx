"use client";

/**
 * Exam chrome for the test player, laid out like the NAATI CCL online test (assessmentQ): a header with the user and
 * an account menu (My preferences) at the top right over a thick coloured line, a breadcrumb bar with the page counter,
 * progress bar and countdown, a page title bar with Help, the page body (with a scroll-down button when it overflows),
 * and a footer with a segmented progress strip and Previous / Next. Three view modes as in the test: Default, Dark
 * and High contrast. Our own logo and name only; nothing here uses NAATI's name or logo.
 */
import { ArrowDown, ArrowLeft, ArrowRight, CameraOff, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Flag, Info, Keyboard, LogOut,
  Play, SlidersHorizontal, Square, Timer, VideoOff, Volume2, X } from "lucide-react";
import Link from "next/link";
import { type CSSProperties, type ReactNode, type RefObject, useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Logo } from "./Logo";
import { BrandName } from "./Theme";
import { cx } from "./ui";

// ------------------------------------------------------------------ view modes (colours of the online test)

export type ViewMode = "default" | "dark" | "contrast";
const MODES: Record<ViewMode, Record<string, string>> = {
  default: {
    bg: "#ffffff", text: "#282c2e", head: "#ffffff", line: "#008d7f", accent: "#008d7f", "on-accent": "#ffffff", heading: "#1abc9c",
    border: "#e3e4e4", panel: "#f2f2f2", track: "#ececec", strip: "#86b5af", todo: "#eceeee", muted: "#535658", outline: "#3c3d3f",
    off: "#d4d5d5", wave: "#9a9c9d", hover: "#f6f7f7", finish: "#c8102e",
  },
  dark: {
    bg: "#282c2e", text: "#eeeeef", head: "#35393b", line: "#809f2e", accent: "#809f2e", "on-accent": "#ffffff", heading: "#1abc9c",
    border: "#43484a", panel: "#35393b", track: "#3a3e40", strip: "#809f2e", todo: "#43484a", muted: "#b9bbbc", outline: "#eeeeef",
    off: "#5b6062", wave: "#8c9091", hover: "#33373a", finish: "#e0414f",
  },
  contrast: {
    bg: "#000000", text: "#ffffff", head: "#000000", line: "#ffffff", accent: "#ffff00", "on-accent": "#000000", heading: "#ffff00",
    border: "#ffffff", panel: "#3a3e40", track: "#3a3e40", strip: "#00e5ff", todo: "#000000", muted: "#ffffff", outline: "#ffffff",
    off: "#6d7072", wave: "#c3c5c5", hover: "#1c1c1c", finish: "#ff4d4d",
  },
};
const MODE_KEY = "exam-view-mode";
const v = (name: string) => `var(--x-${name})`;
const modeStyle = (m: ViewMode) => Object.fromEntries(Object.entries(MODES[m]).map(([k, c]) => [`--x-${k}`, c])) as CSSProperties;

// The chosen mode is kept in this browser (localStorage) and shared by every part of the player.
let modeNow: ViewMode | null = null;
const modeListeners = new Set<() => void>();
function readMode(): ViewMode {
  if (modeNow) return modeNow;
  try {
    const saved = localStorage.getItem(MODE_KEY) as ViewMode | null;
    modeNow = saved && saved in MODES ? saved : "default";
  } catch { modeNow = "default"; /* storage blocked */ }
  return modeNow;
}
function useViewMode(): [ViewMode, (m: ViewMode) => void] {
  const mode = useSyncExternalStore((cb) => { modeListeners.add(cb); return () => { modeListeners.delete(cb); }; }, readMode, () => "default" as ViewMode);
  const save = useCallback((m: ViewMode) => {
    modeNow = m;
    try { localStorage.setItem(MODE_KEY, m); } catch { /* not saved: still applied for this visit */ }
    modeListeners.forEach((cb) => cb());
  }, []);
  return [mode, save];
}

/** Current exam colours for canvas drawing (reads the CSS variables of the nearest .exam root). */
function examColor(el: Element | null, name: string, fallback: string) {
  const root = el?.closest(".exam");
  return (root && getComputedStyle(root).getPropertyValue(`--x-${name}`).trim()) || fallback;
}

// ------------------------------------------------------------------ frame

export type FooterCell = { state: "done" | "current" | "todo" };

export function ExamFrame({ user, crumb, pageNo, pageCount, timer, title, onHelp, cells, onPrev, onNext, prevDisabled, nextDisabled, finish, overlay, children }: {
  user: { name: string; email: string } | null; crumb: string; pageNo: number; pageCount: number; timer: ReactNode;
  title: string; onHelp: () => void; cells: FooterCell[]; onPrev?: () => void; onNext?: () => void; prevDisabled?: boolean;
  nextDisabled?: boolean; finish?: { onClick: () => void; disabled?: boolean }; overlay?: ReactNode; children: ReactNode;
}) {
  const [mode, setMode] = useViewMode();
  const [menu, setMenu] = useState(false);
  const [prefs, setPrefs] = useState(false);
  const main = useRef<HTMLElement>(null);
  const [more, setMore] = useState(false);  // content continues below: show the scroll-down button

  useEffect(() => {
    const el = main.current;
    if (!el) return;
    const check = () => setMore(el.scrollHeight - el.scrollTop - el.clientHeight > 8);
    check();
    el.addEventListener("scroll", check);
    const ro = new ResizeObserver(check);
    ro.observe(el);
    Array.from(el.children).forEach((c) => ro.observe(c));
    return () => { el.removeEventListener("scroll", check); ro.disconnect(); };
  }, [pageNo, children]);
  useEffect(() => { main.current?.scrollTo({ top: 0 }); }, [pageNo]);

  return (
    <div className="exam flex h-screen flex-col text-[14px]" style={{ ...modeStyle(mode), background: v("bg"), color: v("text") }}
      onContextMenu={(e) => e.preventDefault()}>
      <header className="flex h-[70px] shrink-0 items-center justify-between px-5" style={{ background: v("head"), borderBottom: `4px solid ${v("line")}` }}>
        <Logo compact light={mode !== "default"} />
        {user && (
          <div className="relative flex items-center gap-3">
            <div className="text-right leading-tight">
              <div className="text-[15px] font-semibold">{user.name}<span className="hidden md:inline"> ({user.email})</span></div>
              <div className="text-[12px]" style={{ color: v("muted") }}><BrandName /></div>
            </div>
            <button onClick={() => setMenu((m) => !m)} aria-label="Account menu" aria-expanded={menu}
              className="flex size-5 items-center justify-center rounded-full" style={{ background: v("text"), color: v("head") }}>
              <ChevronDown className="size-3.5" strokeWidth={3} />
            </button>
            {menu && <>
              <div className="fixed inset-0 z-20" onClick={() => setMenu(false)} />
              <div className="absolute right-[-8px] top-[42px] z-30 w-[250px] rounded-sm py-1 text-[13px] shadow-lg" style={{ background: v("head"), border: `1px solid ${v("border")}` }}>
                <div className="px-4 py-2 leading-tight">
                  <div>{user.name}</div>
                  <div className="text-[11px]" style={{ color: v("muted") }}>{user.email}</div>
                </div>
                <div style={{ borderTop: `1px solid ${v("border")}` }} />
                <button onClick={() => { setMenu(false); setPrefs(true); }} className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-[var(--x-hover)]">
                  <SlidersHorizontal className="size-4" /> My preferences</button>
                <Link href="/dashboard" className="flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--x-hover)]"><LogOut className="size-4" /> Leave the test</Link>
              </div>
            </>}
          </div>
        )}
      </header>
      <div className="flex h-10 shrink-0 items-center justify-between px-2.5 text-[13px]" style={{ borderBottom: `1px solid ${v("border")}` }}>
        <div className="flex min-w-0 items-center gap-2">
          <span className="max-w-[16ch] truncate">{crumb}</span><span style={{ color: v("muted") }}>/</span><span>Dialogue</span>
        </div>
        <div className="flex items-center gap-10">
          <div className="hidden items-center gap-2 font-semibold tabular-nums sm:flex">
            <span>{pageNo}/{pageCount}</span>
            <div className="h-2.5 w-[120px] overflow-hidden rounded-full" style={{ border: `1px solid ${v("off")}`, background: v("bg") }}>
              <div className="h-full rounded-full" style={{ width: `${(100 * pageNo) / pageCount}%`, background: v("strip") }} />
            </div>
          </div>
          <div className="flex items-center gap-1.5 font-semibold tabular-nums"><Timer className="size-4" /> {timer}</div>
        </div>
      </div>
      <div className="flex h-[50px] shrink-0 items-center justify-between px-4 sm:px-10" style={{ borderBottom: `1px solid ${v("border")}` }}>
        <h1 className="text-[15px] font-semibold">{title}</h1>
        <button onClick={onHelp} className="inline-flex items-center gap-2 text-[13px] font-semibold hover:underline"><CircleHelp className="size-4" /> Help</button>
      </div>
      <div className="relative min-h-0 flex-1">
        <main ref={main} className="h-full overflow-y-auto px-4 py-7 sm:px-10">{children}</main>
        {more && (
          <button onClick={() => main.current?.scrollBy({ top: main.current.clientHeight * 0.8, behavior: "smooth" })} aria-label="Scroll down"
            className="absolute bottom-3 right-6 flex size-10 items-center justify-center rounded-full opacity-75 shadow hover:opacity-100"
            style={{ background: v("accent"), color: v("on-accent") }}><ArrowDown className="size-4" /></button>
        )}
        {overlay}
      </div>
      <footer className="shrink-0">
        <div className="flex gap-0.5" aria-label="Test progress">
          {cells.map((c, i) => (
            <div key={i} className="h-2 flex-1" style={{
              background: c.state === "todo" ? v("todo") : c.state === "current" ? v("accent") : v("strip"),
              outline: mode === "contrast" && c.state === "todo" ? `1px solid ${v("border")}` : undefined, outlineOffset: -1,
            }} />
          ))}
        </div>
        <div className="flex h-[60px] items-center justify-end gap-6 px-4 sm:px-10" style={{ borderTop: `1px solid ${v("border")}` }}>
          <button onClick={onPrev} disabled={prevDisabled || !onPrev}
            className="inline-flex items-center gap-3 text-[13px] font-semibold disabled:text-[var(--x-off)]">
            <ArrowLeft className="size-4" /> Previous</button>
          {finish
            ? <button onClick={finish.onClick} disabled={finish.disabled}
                className="inline-flex h-10 items-center gap-3 rounded-[20px] px-6 text-[13px] font-semibold text-white disabled:opacity-50" style={{ background: v("finish") }}>
                <Flag className="size-4 fill-white" /> Finish</button>
            : <button onClick={onNext} disabled={nextDisabled || !onNext}
                className="inline-flex h-10 w-28 items-center justify-center gap-3 rounded-[20px] text-[13px] font-semibold disabled:opacity-40"
                style={{ background: v("accent"), color: v("on-accent") }}>Next <ArrowRight className="size-4" /></button>}
        </div>
      </footer>
      {prefs && <Preferences onClose={() => setPrefs(false)} mode={mode} onMode={setMode} />}
    </div>
  );
}

/** Shown while the test loads: the header and an "Loading..." spinner over a grey veil, as in the online test. */
export function ExamLoading() {
  const [mode] = useViewMode();
  return (
    <div className="exam relative flex h-screen flex-col" style={{ ...modeStyle(mode), background: v("bg"), color: v("text") }}>
      <header className="flex h-[70px] shrink-0 items-center px-5" style={{ background: v("head"), borderBottom: `4px solid ${v("line")}` }}>
        <Logo compact light={mode !== "default"} />
      </header>
      <div className="h-10 shrink-0" style={{ borderBottom: `1px solid ${v("border")}` }} />
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#282c2e]/75 text-white">
        <span className="size-7 animate-spin rounded-full border-2 border-white border-t-transparent" />
        <span className="text-[13px] italic">Loading...</span>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ preferences

function Preferences({ onClose, mode, onMode }: { onClose: () => void; mode: ViewMode; onMode: (m: ViewMode) => void }) {
  const [tab, setTab] = useState<"view" | "time">("view");
  const [pick, setPick] = useState(mode);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 15000);
    return () => clearInterval(t);
  }, []);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const offset = -now.getTimezoneOffset();
  const utc = `UTC${offset >= 0 ? "+" : "-"}${String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0")}:${String(Math.abs(offset) % 60).padStart(2, "0")}`;
  const stamp = now.toLocaleString("en-AU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "numeric", minute: "2-digit" });
  const save = () => { onMode(pick); onClose(); };
  return (
    <ExamModal open onClose={onClose} title="Preferences" size="lg" actions={<ExamPill onClick={save}>OK</ExamPill>}>
      <div className="-mx-5 -my-5 flex min-h-[340px] flex-col sm:flex-row">
        <nav className="flex shrink-0 gap-1 p-4 sm:w-[234px] sm:flex-col" style={{ background: v("hover") }}>
          {([["view", "Interface options"], ["time", "Time"]] as const).map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)} className="rounded-sm px-4 py-2 text-left text-[14px]"
              style={tab === k ? { background: v("strip"), color: "#fff" } : undefined}>{label}</button>
          ))}
        </nav>
        <div className="flex-1 p-5">
          {tab === "view" && <>
            <h3 className="text-[16px]">Interface options</h3>
            <p className="mt-4 font-semibold">View mode</p>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              {(["default", "dark", "contrast"] as ViewMode[]).map((m) => (
                <label key={m} className="cursor-pointer rounded-sm p-5" style={{ border: `1px solid ${v("border")}`, background: pick === m ? v("hover") : undefined }}>
                  <ModePreview mode={m} />
                  <span className="mt-4 flex items-center gap-2 text-[14px]">
                    <input type="radio" name="view-mode" checked={pick === m} onChange={() => setPick(m)} className="size-4" style={{ accentColor: MODES.default.outline }} />
                    {m === "default" ? "Default" : m === "dark" ? "Dark" : "High contrast"}
                  </span>
                </label>
              ))}
            </div>
          </>}
          {tab === "time" && <>
            <h3 className="text-[16px]">Time</h3>
            <p className="mt-4 font-semibold">Time zone</p>
            <p className="mt-2 flex items-center gap-2"><span className="inline-flex h-5 w-9 items-center justify-end rounded-full px-0.5" style={{ background: v("strip") }}><span className="size-4 rounded-full bg-white" /></span> Detect automatically</p>
            <p className="mt-2" style={{ color: v("muted") }}>{utc} ({tz.replace(/_/g, " ")})</p>
            <InfoBox>Current time: <b>{stamp}</b></InfoBox>
            <p className="mt-4 font-semibold">Locale</p>
            <div className="mt-2 w-full max-w-[330px] rounded-sm px-3 py-2" style={{ border: `1px solid ${v("off")}` }}>English (Australia)</div>
            <InfoBox>The locale defines the formatting of dates and numbers.<br />Current date format: <b>{stamp}</b><br />Current number format: <b>{(1000000.01).toLocaleString("en-AU")}</b></InfoBox>
          </>}
        </div>
      </div>
    </ExamModal>
  );
}

function InfoBox({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 flex items-center gap-4 rounded-sm px-4 py-3" style={{ background: v("hover") }}>
      <span className="flex size-5 shrink-0 items-center justify-center rounded-full" style={{ background: v("text"), color: v("bg") }}><Info className="size-3" strokeWidth={3} /></span>
      <div>{children}</div>
    </div>
  );
}

/** Small picture of a view mode, like the cards in the test's Preferences. */
function ModePreview({ mode }: { mode: ViewMode }) {
  const c = MODES[mode];
  const box = (style: CSSProperties) => <span className="absolute" style={style} />;
  return (
    <span className="relative block h-[95px] w-full" style={{ background: c.bg, border: "1px solid #d4d5d5" }}>
      {box({ left: 0, right: 0, top: 0, height: 10, background: c.head })}
      {box({ left: 4, top: 3, width: 12, height: 4, background: c.text })}
      {box({ left: 0, top: 10, width: "25%", bottom: 0, background: c.panel })}
      {box({ left: "24%", top: 22, width: 2, height: 8, background: c.accent })}
      {box({ left: "30%", top: 18, width: "24%", height: 18, background: c.track })}
      {[24, 31, 38].map((t) => <span key={t} className="absolute" style={{ left: "58%", top: t, width: "34%", height: 4, background: c.track }} />)}
      {[50, 58, 66].map((t) => <span key={t} className="absolute" style={{ left: "30%", top: t, width: "62%", height: 5, background: c.track }} />)}
      {box({ left: "30%", bottom: 6, width: "10%", height: 5, background: c.accent })}
      {box({ right: "16%", bottom: 6, width: "10%", height: 5, border: `1px solid ${c.text}` })}
      {box({ right: "4%", bottom: 6, width: "10%", height: 5, border: `1px solid ${c.text}` })}
    </span>
  );
}

// ------------------------------------------------------------------ page content pieces

/** Page heading in the test's colour ("INFORMATION FOR CANDIDATES", "Filipino CCL test"). */
export function ExamHeading({ children, upper }: { children: ReactNode; upper?: boolean }) {
  return <h2 className={cx("font-bold", upper ? "text-[16px] uppercase" : "text-[18px]")} style={{ color: v("heading") }}>{children}</h2>;
}

/** The look of a button, used inside instructions ("Click [Start] and speak after the chime"). */
export function InlineBtn({ children, outline }: { children: ReactNode; outline?: boolean }) {
  return <span className="mx-2 inline-flex h-[50px] items-center justify-center rounded-[25px] px-7 align-middle text-[15px] font-semibold"
    style={outline ? { border: `1px solid ${v("outline")}`, background: v("bg") } : { background: v("accent"), color: v("on-accent") }}>{children}</span>;
}

/** Small round Next icon, as in "Please click Next (→) to start". */
export function InlineNext() {
  return <span className="mx-1 inline-flex size-7 items-center justify-center rounded-full border align-middle" style={{ borderColor: v("accent"), color: v("accent") }}><ArrowRight className="size-3.5" /></span>;
}

/** Small red Finish pill, as in "Please click on [Finish] at the bottom of the screen". */
export function InlineFinish() {
  return <span className="mx-1 inline-flex h-6 items-center gap-1.5 rounded-full border px-4 align-middle text-[10px]" style={{ borderColor: v("finish"), color: v("finish") }}><Flag className="size-3" style={{ fill: v("finish") }} /> Finish</span>;
}

/** Text from config with **bold** parts. */
export function Rich({ text }: { text: string }) {
  return <>{text.split("**").map((part, i) => (i % 2 ? <b key={i}>{part}</b> : part))}</>;
}

// ------------------------------------------------------------------ controls

export function StartButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled} data-space
    className="inline-flex h-10 min-w-[90px] items-center justify-center rounded-[20px] border px-5 text-[13px] font-semibold disabled:!border-[var(--x-off)] disabled:!bg-transparent disabled:!text-[var(--x-off)]"
    style={{ background: v("accent"), borderColor: v("accent"), color: v("on-accent") }}>Start</button>;
}

export function FinishButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled} data-space
    className="inline-flex h-10 items-center rounded-[20px] border px-5 text-[13px] font-semibold hover:bg-[var(--x-hover)] disabled:!border-[var(--x-off)] disabled:!text-[var(--x-off)]"
    style={{ borderColor: v("outline") }}>Finish attempt</button>;
}

/** Round outline icon button (Play / Stop, previous / next segment on the example segment). */
export function RoundBtn({ onClick, disabled, label, small, children }: { onClick?: () => void; disabled?: boolean; label: string; small?: boolean; children: ReactNode }) {
  return <button onClick={onClick} disabled={disabled || !onClick} aria-label={label} title={label}
    className={cx("inline-flex items-center justify-center rounded-full border hover:bg-[var(--x-hover)] disabled:!border-[var(--x-off)] disabled:!text-[var(--x-off)]", small ? "size-6" : "size-10")}
    style={{ borderColor: v("wave") }}>{children}</button>;
}
export const PlayIcon = () => <Play className="size-3.5 fill-current" />;
export const StopIcon = () => <Square className="size-3 fill-current" />;
export const PrevSegIcon = () => <ChevronLeft className="size-3.5" />;
export const NextSegIcon = () => <ChevronRight className="size-3.5" />;

/** Keyboard icon at the right of the controls; shows the space-bar shortcut. */
export function KeyboardHint() {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative">
      <button onClick={() => setOpen((o) => !o)} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onBlur={() => setOpen(false)}
        aria-label="Keyboard shortcuts" className="flex"><Keyboard className="size-5" /></button>
      {open && (
        <span className="absolute bottom-8 right-0 z-10 w-max rounded-sm px-5 py-3 text-[13px] shadow-lg"
          style={{ background: v("head"), border: `1px solid ${v("border")}` }}>Press the space bar to start and stop the recording</span>
      )}
    </span>
  );
}

// ------------------------------------------------------------------ media

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
    <div className="relative mx-auto flex aspect-[4/3] w-full max-w-[320px] items-center justify-center overflow-hidden rounded border-2"
      style={{ background: v("panel"), borderColor: recording ? "#f43f5e" : v("off") }}>
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
        : (issue || onRetry) && <div className="flex flex-col items-center gap-1.5 px-4 text-center text-[12px]" style={{ color: v("muted") }}>
            <CameraOff className="size-6" /> <span className="font-semibold">Camera off</span>
            {issue && <span className="leading-snug">{issue}</span>}
            {onRetry && !recording && <button onClick={onRetry} className="mt-1 rounded-full px-3 py-1 font-semibold" style={{ border: `1px solid ${v("off")}`, background: v("bg") }}>Turn camera on</button>}
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
        <div className="flex w-6 shrink-0 justify-center py-1.5" style={{ background: v("panel") }}>
          <input type="range" min={0} max={1} step={0.05} value={volume} onChange={(e) => onVolume(Number(e.target.value))}
            aria-label="Volume" className="h-full" style={{ writingMode: "vertical-lr", direction: "rtl", accentColor: v("accent") }} />
        </div>
        <div className="relative flex-1 overflow-hidden" style={{ background: v("panel") }}>
          {/* eslint-disable-next-line @next/next/no-img-element -- protected image from the API, not next/image */}
          {src && <img src={src} alt="" draggable={false} className="size-full object-fill opacity-40 grayscale" />}
          {!src && <div className="absolute inset-x-0 top-1/2 h-px" style={{ background: v("wave") }} />}
          <div className="absolute inset-y-0 left-0 w-0.5" style={{ background: v("outline") }} />
          <div className="absolute inset-y-0 right-0 w-px bg-[#f36b7f]" />
          <div className="absolute right-0 top-0 h-4 w-2.5 rounded-b-sm bg-[#f36b7f]" />
          {progress > 0 && <div className="absolute inset-y-0 w-0.5" style={{ left: `${Math.min(100, progress * 100)}%`, background: v("accent") }} />}
        </div>
      </div>
    </div>
  );
}

/**
 * Recording row: a live trace of the microphone level, drawn from samplesRef (0..1, one every ~50 ms) across the
 * timeline, on the grey track.
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
    g.strokeStyle = recording ? examColor(c, "accent", "#008d7f") : examColor(c, "wave", "#9a9c9d");
    g.lineWidth = devicePixelRatio * 1.5;
    g.beginPath();
    const step = w / capacity;
    s.slice(-capacity).forEach((x, i) => {
      const amp = Math.max(0.01, x) * h * 0.45;
      g.moveTo(i * step, h / 2 - amp);
      g.lineTo(i * step, h / 2 + amp);
    });
    g.stroke();
  }, [samplesRef, capacity, recording, tick]);
  return <div className="ml-6 h-16 overflow-hidden" style={{ background: v("track") }}><canvas ref={canvas} className="size-full" /></div>;
}

// ------------------------------------------------------------------ popups

/** Popup in the online test's style: title with a close cross, body, buttons at the bottom right. */
export function ExamModal({ open, onClose, title, children, actions, size }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; actions?: ReactNode; size?: "lg";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" onMouseDown={(e) => e.stopPropagation()}
        className={cx("max-h-full w-full overflow-y-auto rounded-sm shadow-xl", size === "lg" ? "max-w-[914px]" : "max-w-[454px]")}
        style={{ background: v("head"), color: v("text") }}>
        {typeof title === "string"
          ? <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: `1px solid ${v("border")}` }}>
              <h2 className="text-[22px] font-light">{title}</h2>
              <button onClick={onClose} aria-label="Close"><X className="size-4" strokeWidth={3} /></button>
            </div>
          : title}
        <div className="px-5 py-5 text-[13px] leading-relaxed">{children}</div>
        {actions && <div className="flex items-center justify-end gap-6 px-5 py-3" style={{ borderTop: `1px solid ${v("border")}` }}>{actions}</div>}
      </div>
    </div>
  );
}

/** Pill button in the accent colour (OK / Close in popups). */
export function ExamPill({ onClick, children, disabled }: { onClick: () => void; children: ReactNode; disabled?: boolean }) {
  return <button onClick={onClick} disabled={disabled} className="inline-flex h-[30px] min-w-[90px] items-center justify-center rounded-[15px] px-5 text-[13px] font-semibold disabled:opacity-50"
    style={{ background: v("accent"), color: v("on-accent") }}>{children}</button>;
}
export function ExamTextBtn({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return <button onClick={onClick} className="text-[13px] font-semibold hover:underline">{children}</button>;
}

/** Status icon for a row of the End of dialogue list. */
export function RowIcon({ info }: { info?: boolean }) {
  return info
    ? <span className="flex size-[18px] items-center justify-center rounded-full" style={{ background: v("muted"), color: v("head") }}><Info className="size-3" strokeWidth={3} /></span>
    : <span className="flex size-[18px] items-center justify-center rounded-full border-2" style={{ borderColor: v("muted") }}><span className="size-1.5 rounded-full" style={{ background: v("muted") }} /></span>;
}

/** Exam colours as CSS variables, for pages that style themselves (var(--x-accent) etc.). */
export const XC = { accent: v("accent"), muted: v("muted"), heading: v("heading"), text: v("text"), bg: v("bg"), hover: v("hover"), border: v("border") };

export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
export const hhmmss = (s: number) => {
  const t = Math.max(0, Math.floor(s));
  return [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60].map((n) => String(n).padStart(2, "0")).join(":");
};
