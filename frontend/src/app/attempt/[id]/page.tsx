"use client";

import Hls from "hls.js";
import { AlertTriangle, ArrowRight, CheckCircle2, Headphones, Loader2, Mic, MicOff, Repeat, Square, X } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Logo } from "@/components/AppShell";
import SegmentFeedback from "@/components/SegmentFeedback";
import { Badge, Button, Card, cx, ErrorNote, Spinner } from "@/components/ui";
import { api, ApiError, LANG, type SegmentResult } from "@/lib/api";
import { BrowserStt, browserSttSupported } from "@/lib/browserStt";

type Current = {
  index: number; dialogue_position: number; segment_number: number; speaker: "en" | "hi"; speaker_role: string;
  target_language: "en" | "hi"; plays: number; max_plays: number; repeat_will_deduct: boolean;
};
type AttemptState = {
  id: string; mode: "practice" | "mock"; status: string; total: number; index: number;
  dialogues: { id: string; title: string; domain: string; scenario: string; segment_count: number; start_index: number; repeats_used: number }[];
  current: Current | null; response_window_seconds: number; free_repeats_per_dialogue: number;
  stt_provider: string; marker: string;
  language: { code: string; name: string; native: string } | null; stt_locales: Record<string, string>;
};
type Phase = "loading" | "intro" | "dialogueIntro" | "playing" | "heard" | "recording" | "uploading" | "feedback" | "done" | "error";

function pickMime() {
  const opts = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return opts.find((m) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m)) ?? "";
}

export default function Player() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [st, setSt] = useState<AttemptState | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState("");
  const [micOk, setMicOk] = useState(false);
  const [micState, setMicState] = useState<"idle" | "testing" | "playback" | "denied">("idle");
  const [progress, setProgress] = useState({ t: 0, d: 0 });
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [level, setLevel] = useState(0);
  const [instantFeedback, setInstantFeedback] = useState(true);
  const [feedback, setFeedback] = useState<SegmentResult | null>(null);
  const [lastIndex, setLastIndex] = useState<number | null>(null);
  const [liveText, setLiveText] = useState("");
  const [sttActive, setSttActive] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const discardRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const rafRef = useRef<number>(0);
  const ctxRef = useRef<AudioContext | null>(null);
  const sttRef = useRef<BrowserStt | null>(null);
  const phaseRef = useRef<Phase>("loading");
  const stRef = useRef<AttemptState | null>(null);
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  const loadState = useCallback(async () => {
    const s = await api<AttemptState>(`/attempts/${id}/state`);
    stRef.current = s;
    setSt(s);
    return s;
  }, [id]);

  // ---------------------------------------------------------------- boot
  useEffect(() => {
    api<AttemptState>(`/attempts/${id}/state`).then((s) => {
      stRef.current = s;
      setSt(s);
      if (s.status !== "in_progress") { router.replace(`/results/${id}`); return; }
      if (s.index > 0 || (s.current?.plays ?? 0) > 0) {
        api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "reload", detail: `resumed at ${s.index}` } }).catch(() => {});
      }
      setPhase("intro");
    }).catch((e) => { setError((e as Error).message); setPhase("error"); });
    return () => {
      hlsRef.current?.destroy();
      sttRef.current?.abort();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (timerRef.current) clearInterval(timerRef.current);
      cancelAnimationFrame(rafRef.current);
    };
  }, [id, router]);

  // Integrity: tab switches are logged (not blocked) while the test is live.
  useEffect(() => {
    const onVis = () => {
      if (document.hidden && ["playing", "recording", "heard"].includes(phaseRef.current)) {
        api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "tab_blur" } }).catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [id]);

  // ---------------------------------------------------------------- mic
  const getMic = async () => {
    if (streamRef.current) return streamRef.current;
    const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    streamRef.current = s;
    return s;
  };

  const micCheck = async () => {
    try {
      const stream = await getMic();
      setMicState("testing");
      const rec = new MediaRecorder(stream, pickMime() ? { mimeType: pickMime() } : undefined);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        const url = URL.createObjectURL(new Blob(chunks, { type: rec.mimeType }));
        const a = new Audio(url);
        setMicState("playback");
        a.onended = () => { setMicState("idle"); setMicOk(true); };
        a.play().catch(() => { setMicState("idle"); setMicOk(true); });
      };
      startMeter(stream);
      rec.start();
      setTimeout(() => { rec.stop(); stopMeter(); }, 3000);
    } catch {
      setMicState("denied");
      api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "mic_denied" } }).catch(() => {});
    }
  };

  const startMeter = (stream: MediaStream) => {
    ctxRef.current?.close().catch(() => {});
    const ctx = new AudioContext();
    ctxRef.current = ctx;
    const src = ctx.createMediaStreamSource(stream);
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    src.connect(an);
    const buf = new Uint8Array(an.fftSize);
    const tick = () => {
      an.getByteTimeDomainData(buf);
      let peak = 0;
      for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
      setLevel(Math.min(1, peak / 60));
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
  };
  const stopMeter = () => { cancelAnimationFrame(rafRef.current); setLevel(0); };

  // ---------------------------------------------------------------- playback
  const play = async () => {
    setError("");
    let url: string;
    try {
      const r = await api<{ url: string }>(`/attempts/${id}/play`, { method: "POST" });
      url = r.url;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) { await loadState(); setPhase("heard"); return; }
      setError((e as Error).message);
      return;
    }
    await loadState();
    const audio = audioRef.current!;
    hlsRef.current?.destroy();
    setProgress({ t: 0, d: 0 });
    setPhase("playing");
    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true });
      hlsRef.current = hls;
      hls.on(Hls.Events.MANIFEST_PARSED, () => { audio.play().catch(() => setError("Tap anywhere to allow audio, then press Repeat.")); });
      hls.on(Hls.Events.ERROR, (_e, data) => { if (data.fatal) { setError("Audio stream failed. Use Repeat to try again."); setPhase("heard"); } });
      hls.loadSource(url);
      hls.attachMedia(audio);
    } else if (audio.canPlayType("application/vnd.apple.mpegurl")) {
      audio.src = url;
      audio.play().catch(() => setError("Tap to allow audio."));
    } else {
      setError("This browser can't play the test audio. Please use Chrome, Edge, Firefox or Safari.");
    }
  };

  const onEnded = () => {
    hlsRef.current?.destroy();
    hlsRef.current = null;
    startRecording();
  };

  // ---------------------------------------------------------------- recording
  const startRecording = async () => {
    const s = stRef.current!;
    let stream: MediaStream;
    try { stream = await getMic(); } catch { setMicState("denied"); setPhase("heard"); return; }
    chunksRef.current = [];
    discardRef.current = false;
    const mime = pickMime();
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    recRef.current = rec;
    rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data); };
    const useBrowserStt = s.stt_provider === "mock" && browserSttSupported();
    const stt = useBrowserStt ? new BrowserStt(setLiveText) : null;
    sttRef.current = stt;
    setSttActive(!!stt);
    setLiveText("");
    rec.onstop = async () => {
      stopMeter();
      if (timerRef.current) clearInterval(timerRef.current);
      if (discardRef.current) { stt?.abort(); return; }
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
      setPhase("uploading");
      const bt = stt ? await stt.stop() : null;
      upload(blob, bt);
    };
    rec.start(250);
    const tgt = s.current!.target_language;
    stt?.start(s.stt_locales[tgt] ?? (tgt === "en" ? "en-IN" : "hi-IN"));
    startMeter(stream);
    setSecondsLeft(s.response_window_seconds);
    setPhase("recording");
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setSecondsLeft((x) => {
        if (x <= 1) { stopRecording(); return 0; }
        return x - 1;
      });
    }, 1000);
  };

  const stopRecording = () => {
    if (recRef.current && recRef.current.state !== "inactive") recRef.current.stop();
  };

  const repeat = () => {
    if (recRef.current && recRef.current.state !== "inactive") {
      discardRef.current = true;
      recRef.current.stop();
    }
    play();
  };

  const upload = async (blob: Blob, bt: { text: string; confidence: number | null } | null) => {
    const s = stRef.current!;
    const idx = s.current!.index;
    setPhase("uploading");
    const fd = new FormData();
    const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
    fd.append("audio", blob, `segment-${idx}.${ext}`);
    if (bt) {
      fd.append("browser_stt", "true");
      fd.append("browser_transcript", bt.text);
      if (bt.confidence !== null) fd.append("browser_confidence", String(bt.confidence));
    }
    try {
      const r = await api<{ done: boolean; next_index: number }>(`/attempts/${id}/segments/${idx}/audio`, { method: "POST", body: fd });
      setLastIndex(idx);
      const next = await loadState();
      if (r.done) { setPhase("done"); return; }
      if (s.mode === "practice" && instantFeedback) { setFeedback(null); setPhase("feedback"); pollFeedback(idx); return; }
      advance(next);
    } catch (e) {
      setError(`Upload failed: ${(e as Error).message}`);
      setPhase("heard");
    }
  };

  const advance = (s: AttemptState) => {
    if (!s.current) { setPhase("done"); return; }
    if (s.current.segment_number === 1 && s.current.plays === 0) { setPhase("dialogueIntro"); return; }
    setTimeout(() => play(), 700);
  };

  const pollFeedback = async (idx: number) => {
    for (let i = 0; i < 60; i++) {
      try {
        const f = await api<SegmentResult>(`/attempts/${id}/segments/${idx}/feedback`);
        if (f.response && (f.response.marking || f.response.status === "error")) { setFeedback(f); return; }
      } catch {}
      await new Promise((r) => setTimeout(r, 1000));
    }
  };

  // When done, wait for marking then go to results.
  useEffect(() => {
    if (phase !== "done") return;
    let alive = true;
    (async () => {
      for (let i = 0; i < 120 && alive; i++) {
        try {
          const r = await api<{ status: string }>(`/attempts/${id}/results`);
          if (r.status === "marked") { router.replace(`/results/${id}`); return; }
        } catch {}
        await new Promise((r) => setTimeout(r, 1000));
      }
    })();
    return () => { alive = false; };
  }, [phase, id, router]);

  const endEarly = async () => {
    if (!confirm("End the test now? Segments you haven't done will count as unanswered.")) return;
    discardRef.current = true;
    stopRecording();
    hlsRef.current?.destroy();
    audioRef.current?.pause();
    await api(`/attempts/${id}/submit`, { method: "POST" });
    setPhase("done");
  };

  // ---------------------------------------------------------------- render
  if (phase === "loading" || !st) return <Spinner label="Loading test" />;
  if (phase === "error") return <div className="mx-auto max-w-lg p-8"><ErrorNote>{error}</ErrorNote></div>;

  const cur = st.current;
  const dlg = cur ? st.dialogues[cur.dialogue_position] : st.dialogues[st.dialogues.length - 1];
  const playsLeft = cur ? cur.max_plays - cur.plays : 0;
  const LN = st.language?.name ?? "Hindi";

  const begin = () => {
    if (!cur) return;
    if (cur.plays > 0) setPhase("heard");
    else if (cur.segment_number === 1) setPhase("dialogueIntro");
    else play();
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-100" onContextMenu={(e) => e.preventDefault()}>
      {/* Hidden, control-less audio element: no seek bar, no scrubbing, no download menu. */}
      <audio ref={audioRef} onEnded={onEnded} controls={false} controlsList="nodownload noplaybackrate"
        onTimeUpdate={(e) => setProgress({ t: e.currentTarget.currentTime, d: e.currentTarget.duration || 0 })}
        className="hidden" />

      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
        <Logo />
        <div className="flex items-center gap-3">
          <Badge tone={st.mode === "mock" ? "violet" : "brand"}>{st.mode === "mock" ? "Mock test" : "Practice"}</Badge>
          {cur && <span className="hidden text-sm tabular-nums text-slate-500 sm:inline">Segment {cur.index + 1} of {st.total}</span>}
          {phase !== "intro" && phase !== "done" && (
            <Button variant="ghost" size="sm" onClick={endEarly}><X className="size-4" /> End</Button>
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">
        {/* dialogue progress */}
        {phase !== "intro" && (
          <div className="mb-6 space-y-3">
            {st.dialogues.map((d, di) => (
              <div key={d.id}>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className={cx("font-medium", di === cur?.dialogue_position ? "text-ink" : "text-slate-400")}>
                    Dialogue {di + 1}: {d.title}
                  </span>
                  <span className="text-slate-400">Repeats used: {d.repeats_used} (free: {st.free_repeats_per_dialogue})</span>
                </div>
                <div className="flex gap-1">
                  {Array.from({ length: d.segment_count }).map((_, i) => {
                    const gi = d.start_index + i;
                    return <div key={i} className={cx("h-1.5 flex-1 rounded-full",
                      gi < st.index ? "bg-brand-500" : gi === st.index && phase !== "done" ? "bg-amber-400" : "bg-slate-300/70")} />;
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}

        {phase === "intro" && (
          <Card className="p-6 sm:p-8">
            <h1 className="text-xl font-semibold">{st.mode === "mock" ? "Mock test" : "Practice dialogue"}</h1>
            <p className="mt-1 text-sm text-slate-500">{st.dialogues.map((d) => d.title).join(" · ")}</p>
            {st.index > 0 || (cur?.plays ?? 0) > 0 ? (
              <div className="mt-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Resuming at segment {st.index + 1} of {st.total}. Segments you&apos;ve already heard won&apos;t replay.
              </div>
            ) : null}

            <div className="mt-6 rounded-xl bg-brand-50 p-5">
              <div className="text-sm font-semibold text-brand-900">Your role: you are the interpreter</div>
              <p className="mt-1 text-sm text-brand-900/80">
                You&apos;ll hear a conversation between an English speaker and a {LN} speaker. They can&apos;t understand each other.
                After each line, <b>say the same thing in the other language</b> so the other person understands.
                Don&apos;t answer the question and don&apos;t add anything. Pass on exactly what was said.
              </p>
              <div className="mt-4 overflow-hidden rounded-lg bg-white text-sm ring-1 ring-brand-100">
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-slate-100 px-4 py-3">
                  <div><div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">You hear (English)</div>
                    <div className="mt-0.5">&ldquo;When did the pain start?&rdquo;</div></div>
                  <ArrowRight className="size-4 text-brand-500" />
                  <div><div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">You say ({LN})</div>
                    <div className="hindi mt-0.5" lang="hi">&ldquo;दर्द कब शुरू हुआ?&rdquo;</div></div>
                </div>
                <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 py-3">
                  <div><div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">You hear ({LN})</div>
                    <div className="hindi mt-0.5" lang="hi">&ldquo;कल रात से, डॉक्टर साहब।&rdquo;</div></div>
                  <ArrowRight className="size-4 text-brand-500" />
                  <div><div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">You say (English)</div>
                    <div className="mt-0.5">&ldquo;Since last night, doctor.&rdquo;</div></div>
                </div>
              </div>
              <p className="mt-3 text-xs text-brand-900/70">
                Not &ldquo;It started last night&rdquo;. That would be answering the question, not interpreting it.
              </p>
            </div>

            <div className="mt-6 text-sm font-semibold">How each segment works</div>
            <ol className="mt-3 space-y-3 text-sm text-slate-600">
              <li className="flex gap-3"><Headphones className="size-5 shrink-0 text-brand-600" />
                <span><b className="text-ink">Listen.</b> The segment plays once. You can&apos;t pause, rewind or skip ahead, so take notes if it helps.</span></li>
              <li className="flex gap-3"><Mic className="size-5 shrink-0 text-brand-600" />
                <span><b className="text-ink">Speak after the chime.</b> Recording starts by itself. Interpret into the other language, then press <b>Done</b>. You have {st.response_window_seconds} seconds.</span></li>
              <li className="flex gap-3"><Repeat className="size-5 shrink-0 text-brand-600" />
                <span><b className="text-ink">Missed something?</b> Press <b>Repeat</b> once to hear it again. One repeat per dialogue is free, and extra repeats cost marks.</span></li>
              <li className="flex gap-3"><CheckCircle2 className="size-5 shrink-0 text-brand-600" />
                <span><b className="text-ink">Scoring.</b> Numbers, names, dates and every detail count. {st.mode === "mock"
                  ? "Each dialogue is marked out of 45. To pass you need 63/90 overall and at least 29 in each dialogue."
                  : "You'll see feedback on what you said after each segment."}</span></li>
            </ol>
            <div className="mt-8 rounded-xl border border-slate-200 p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-medium">Microphone check</div>
                  <div className="text-xs text-slate-500">
                    {micState === "testing" ? "Say something… recording 3 seconds" : micState === "playback" ? "Playing back your voice" :
                      micOk ? "Microphone works" : "Record 3 seconds and hear it back"}
                  </div>
                </div>
                {micOk ? <Badge tone="green"><CheckCircle2 className="size-3" /> Ready</Badge> :
                  <Button variant="secondary" size="sm" onClick={micCheck} loading={micState === "testing" || micState === "playback"}><Mic className="size-4" /> Test mic</Button>}
              </div>
              {micState === "testing" && <LevelMeter level={level} />}
              {micState === "denied" && (
                <div className="mt-4 flex gap-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
                  <MicOff className="size-4 shrink-0" />
                  Microphone access was blocked. Click the lock icon in the address bar, allow the microphone, then reload this page.
                </div>
              )}
            </div>
            <div className="mt-6 flex items-center justify-between">
              {st.mode === "practice" ? (
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input type="checkbox" checked={instantFeedback} onChange={(e) => setInstantFeedback(e.target.checked)} className="accent-brand-600" />
                  Show feedback after each segment
                </label>
              ) : <span className="text-xs text-slate-500">Feedback is shown after the whole test.</span>}
              <Button size="lg" disabled={!micOk} onClick={begin}>{st.index > 0 || (cur?.plays ?? 0) > 0 ? "Resume" : "Start"}</Button>
            </div>
          </Card>
        )}

        {phase === "dialogueIntro" && dlg && (
          <Card className="p-8 text-center">
            <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Dialogue {cur!.dialogue_position + 1} of {st.dialogues.length}</div>
            <h2 className="mt-2 text-2xl font-semibold">{dlg.title}</h2>
            <p className="mx-auto mt-3 max-w-lg text-slate-600">{dlg.scenario}</p>
            <p className="mt-2 text-sm text-slate-500">{dlg.segment_count} segments · {dlg.domain}</p>
            <Button size="lg" className="mt-8" onClick={play}>Begin dialogue</Button>
          </Card>
        )}

        {(phase === "playing" || phase === "heard" || phase === "recording" || phase === "uploading") && cur && (
          <Card className="overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="text-sm text-slate-500">Segment {cur.segment_number} of {dlg.segment_count}</div>
                <Badge>{LANG[cur.speaker]} → {LANG[cur.target_language]}</Badge>
              </div>
            </div>
            <div className="flex flex-col items-center px-6 py-12">
              {phase === "playing" && (
                <>
                  <div className="flex h-16 items-end gap-1.5">
                    {[0, 1, 2, 3, 4].map((i) => <div key={i} className="speaking-bar w-2.5 rounded-full bg-brand-500" style={{ height: 64, animationDelay: `${i * 0.12}s` }} />)}
                  </div>
                  <div className="mt-5 text-lg font-medium">{cur.speaker_role} is speaking</div>
                  <div className="text-sm text-slate-500">{LANG[cur.speaker]}{cur.plays > 1 ? " · repeat" : ""}</div>
                  {/* Progress only. Not a slider, can't be dragged. */}
                  <div className="mt-8 w-full max-w-sm">
                    <div className="h-1.5 overflow-hidden rounded-full bg-slate-200" aria-hidden>
                      <div className="h-full bg-brand-500 transition-[width] duration-300" style={{ width: progress.d ? `${(progress.t / progress.d) * 100}%` : "0%" }} />
                    </div>
                    <div className="mt-1 text-right text-xs tabular-nums text-slate-400">{progress.t.toFixed(0)}s</div>
                  </div>
                </>
              )}

              {phase === "recording" && (
                <>
                  <div className="relative flex size-20 items-center justify-center">
                    <span className="absolute inset-0 animate-ping rounded-full bg-rose-400/30" />
                    <span className="relative flex size-16 items-center justify-center rounded-full bg-rose-500 text-white"><Mic className="size-7" /></span>
                  </div>
                  <div className="mt-5 text-lg font-medium">Interpret into {LANG[cur.target_language]}</div>
                  <div className={cx("text-sm tabular-nums", secondsLeft <= 5 ? "font-semibold text-rose-600" : "text-slate-500")}>{secondsLeft}s left</div>
                  <div className="mt-4 w-full max-w-xs"><LevelMeter level={level} /></div>
                  {st.mode === "practice" && sttActive && (
                    <p className={cx("mt-4 min-h-6 max-w-lg text-center text-sm text-slate-500", cur.target_language === "hi" && "hindi")}>
                      {liveText || <span className="italic text-slate-400">Listening…</span>}
                    </p>
                  )}
                  <div className="mt-8 flex flex-wrap justify-center gap-3">
                    <Button size="lg" onClick={stopRecording}><Square className="size-4" /> Done</Button>
                    {playsLeft > 0 && (
                      <Button size="lg" variant="secondary" onClick={repeat}><Repeat className="size-4" /> Repeat segment</Button>
                    )}
                  </div>
                  {playsLeft > 0 && cur.repeat_will_deduct && <p className="mt-3 text-xs text-amber-700">You&apos;ve used your free repeat for this dialogue. Another one will cost marks.</p>}
                </>
              )}

              {phase === "heard" && (
                <>
                  <Headphones className="size-10 text-slate-400" />
                  <div className="mt-4 text-lg font-medium">You&apos;ve already heard this segment</div>
                  <p className="mt-1 max-w-sm text-center text-sm text-slate-500">
                    {playsLeft > 0 ? "Interpret it now, or use your repeat." : "No plays left. Interpret what you remember."}
                  </p>
                  <div className="mt-8 flex gap-3">
                    <Button size="lg" onClick={startRecording}><Mic className="size-4" /> Start recording</Button>
                    {playsLeft > 0 && <Button size="lg" variant="secondary" onClick={play}><Repeat className="size-4" /> Repeat</Button>}
                  </div>
                </>
              )}

              {phase === "uploading" && (
                <div className="flex items-center gap-2 text-slate-500"><Loader2 className="size-5 animate-spin" /> Saving your answer…</div>
              )}
            </div>
          </Card>
        )}

        {phase === "feedback" && lastIndex !== null && (
          <Card className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold">Segment feedback</h2>
              <Button onClick={() => st && advance(st)}>Next segment</Button>
            </div>
            {feedback ? <SegmentFeedback seg={feedback} attemptId={id} /> : <Spinner label="Transcribing and marking" />}
          </Card>
        )}

        {phase === "done" && (
          <Card className="p-10 text-center">
            <Loader2 className="mx-auto size-8 animate-spin text-brand-500" />
            <h2 className="mt-4 text-xl font-semibold">Marking your interpretation</h2>
            <p className="mt-1 text-sm text-slate-500">Transcribing each segment and checking it against the marking criteria…</p>
            <Link href={`/results/${id}`} className="mt-6 inline-block text-sm text-brand-600 hover:underline">Go to results</Link>
          </Card>
        )}

        {(st.stt_provider === "mock" || st.marker === "heuristic") && phase !== "done" && (
          <p className="mt-6 flex items-center justify-center gap-1.5 text-center text-xs text-slate-400">
            <AlertTriangle className="size-3.5" /> Demo mode: {st.stt_provider === "mock" ? (browserSttSupported() ? "speech-to-text runs in your browser" : "no speech-to-text available in this browser, so sample transcripts are used") : ""}
            {st.stt_provider === "mock" && st.marker === "heuristic" ? "; " : ""}{st.marker === "heuristic" ? "static marker in place of AI" : ""}.
          </p>
        )}
      </main>
    </div>
  );
}

function LevelMeter({ level }: { level: number }) {
  return (
    <div className="mt-3 flex h-2 gap-0.5">
      {Array.from({ length: 24 }).map((_, i) => (
        <div key={i} className={cx("flex-1 rounded-sm transition-colors", i / 24 < level ? (i > 19 ? "bg-rose-500" : "bg-emerald-500") : "bg-slate-200")} />
      ))}
    </div>
  );
}
