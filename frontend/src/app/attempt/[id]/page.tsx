"use client";

import Hls from "hls.js";
import { CheckCircle2, Headphones, Loader2, Mic, MicOff, Play, Repeat, SkipForward, Square, Volume2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Logo } from "@/components/Logo";
import { Badge, Button, Card, cx, ErrorNote, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { ChunkUploader, pickMime, playTestSound } from "@/lib/recorder";

type Seg = {
  segment_attempt_id: string; number: number; direction: string; source_language: string; target_language: string;
  speaker_role: string; play_count: number; record_count: number; answered: boolean; skipped: boolean; has_waveform: boolean;
};
type Dlg = { dialogue_attempt_id: string; position: number; title: string; description: string; instructions: string; topic: string | null; segments: Seg[] };
type State = {
  id: string; kind: "mock" | "practice"; title: string; status: string; step: string;
  current: { dialogue_attempt_id: string; segment_attempt_id: string } | null;
  config: { max_plays: number; max_record_attempts: number; response_window_seconds: number; information_1: string; information_1_practice: string; information_2: string; max_upload_mb: number };
  dialogues: Dlg[];
};
type Step = "info1" | "info2" | "segment" | "summary" | "submitted";
type Phase = "ready" | "loading" | "playing" | "recording" | "uploading" | "done";
type Pos = { d: number; s: number };

/** Wall-clock ms for recording timestamps (event handlers only). */
const nowMs = () => Date.now();

function findPos(st: State): Pos | null {
  if (!st.current) return null;
  for (let d = 0; d < st.dialogues.length; d++) {
    const s = st.dialogues[d].segments.findIndex((x) => x.segment_attempt_id === st.current!.segment_attempt_id);
    if (s >= 0) return { d, s };
  }
  return null;
}

export default function Player() {
  const { id } = useParams<{ id: string }>();
  const [st, setSt] = useState<State | null>(null);
  const [step, setStepState] = useState<Step>("info1");
  const [pos, setPos] = useState<Pos | null>(null);
  const [phase, setPhase] = useState<Phase>("ready");
  const [error, setError] = useState("");
  const [fatal, setFatal] = useState("");
  const [progress, setProgress] = useState({ t: 0, d: 0 });
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [level, setLevel] = useState(0);
  const [mic, setMic] = useState<"idle" | "recording" | "playback" | "ok" | "denied">("idle");
  const [soundOk, setSoundOk] = useState(false);
  const [busy, setBusy] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const uploaderRef = useRef<ChunkUploader | null>(null);
  const discardRef = useRef(false);
  const timingRef = useRef<Record<string, number>>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const rafRef = useRef(0);
  const ctxRef = useRef<AudioContext | null>(null);
  const phaseRef = useRef<Phase>("ready");
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  const loadState = useCallback(async () => {
    const s = await api<State>(`/attempts/${id}/state`);
    setSt(s);
    return s;
  }, [id]);

  // ---------------------------------------------------------------- boot / resume
  useEffect(() => {
    api<State>(`/attempts/${id}/state`).then((s) => {
      setSt(s);
      if (s.status !== "In Progress") { setStepState("submitted"); return; }
      const p = findPos(s);
      setPos(p);
      const saved = (s.step as Step) || "info1";
      // Equipment check is repeated after a reload: the microphone permission has to be granted again.
      setStepState(saved === "segment" || saved === "summary" ? "info2" : saved);
      if (saved !== "info1") api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "reload", detail: saved } }).catch(() => {});
    }).catch((e) => setFatal(e.message));
    return () => {
      hlsRef.current?.destroy();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (timerRef.current) clearInterval(timerRef.current);
      cancelAnimationFrame(rafRef.current);
      ctxRef.current?.close().catch(() => {});
    };
  }, [id]);

  useEffect(() => {
    const onVis = () => {
      if (document.hidden && ["playing", "recording"].includes(phaseRef.current)) {
        api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "tab_blur" } }).catch(() => {});
      }
    };
    const onLeave = (e: BeforeUnloadEvent) => { if (["recording", "uploading"].includes(phaseRef.current)) e.preventDefault(); };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("beforeunload", onLeave);
    return () => { document.removeEventListener("visibilitychange", onVis); window.removeEventListener("beforeunload", onLeave); };
  }, [id]);

  const setStep = (s: Step) => {
    setStepState(s);
    setError("");
    if (s !== "submitted") api(`/attempts/${id}/step`, { method: "POST", json: { step: s } }).catch(() => {});
  };

  // ---------------------------------------------------------------- microphone
  const getMic = async () => {
    if (streamRef.current) return streamRef.current;
    const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    streamRef.current = s;
    return s;
  };

  const startMeter = (stream: MediaStream, onLevel?: (l: number) => void) => {
    ctxRef.current?.close().catch(() => {});
    const ctx = new AudioContext();
    ctxRef.current = ctx;
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Uint8Array(an.fftSize);
    const tick = () => {
      an.getByteTimeDomainData(buf);
      let peak = 0;
      for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
      const l = Math.min(1, peak / 60);
      setLevel(l);
      onLevel?.(l);
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
  };
  const stopMeter = () => { cancelAnimationFrame(rafRef.current); setLevel(0); };

  const micCheck = async () => {
    try {
      const stream = await getMic();
      setMic("recording");
      const mime = pickMime();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stopMeter();
        const a = new Audio(URL.createObjectURL(new Blob(chunks, { type: rec.mimeType })));
        setMic("playback");
        a.onended = () => setMic("ok");
        a.play().catch(() => setMic("ok"));
      };
      startMeter(stream);
      rec.start();
      setTimeout(() => rec.stop(), 4000);
    } catch {
      setMic("denied");
      api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "mic_denied" } }).catch(() => {});
    }
  };

  // ---------------------------------------------------------------- segment: play -> chime -> record
  const cur = st && pos ? st.dialogues[pos.d].segments[pos.s] : null;
  const curDlg = st && pos ? st.dialogues[pos.d] : null;

  const play = async () => {
    if (!cur) return;
    setError("");
    setPhase("loading");
    let url: string;
    try {
      url = (await api<{ url: string }>(`/attempts/${id}/segments/${cur.segment_attempt_id}/play`, { method: "POST" })).url;
    } catch (e) {
      setError((e as Error).message);
      setPhase("ready");
      await loadState();
      return;
    }
    await loadState();
    const audio = audioRef.current!;
    hlsRef.current?.destroy();
    setProgress({ t: 0, d: 0 });
    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true });
      hlsRef.current = hls;
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        audio.play().then(() => setPhase("playing")).catch(() => { setError("Your browser blocked audio. Click Start again."); setPhase("ready"); });
      });
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data.fatal) {
          setError("The audio could not be played. If you have plays left, press Start to try again.");
          setPhase("ready");
          api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "audio_error", detail: data.details } }).catch(() => {});
        }
      });
      hls.loadSource(url);
      hls.attachMedia(audio);
    } else if (audio.canPlayType("application/vnd.apple.mpegurl")) {
      audio.src = url;
      audio.play().then(() => setPhase("playing")).catch(() => { setError("Click Start again to allow audio."); setPhase("ready"); });
    } else {
      setError("This browser cannot play the test audio. Please use a recent Chrome, Edge, Firefox or Safari.");
      setPhase("ready");
    }
  };

  const onEnded = () => {
    hlsRef.current?.destroy();
    hlsRef.current = null;
    timingRef.current = { chime_end_ms: nowMs() };  // the chime is the last thing in the segment audio
    startRecording();
  };

  const startRecording = async () => {
    if (!st || !cur) return;
    let stream: MediaStream;
    try { stream = await getMic(); } catch { setMic("denied"); setError("Microphone access is blocked. Allow it in the address bar, then reload."); setPhase("ready"); return; }
    discardRef.current = false;
    const uploader = new ChunkUploader(`/attempts/${id}/segments/${cur.segment_attempt_id}/recording`);
    uploaderRef.current = uploader;
    const mime = pickMime();
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    recRef.current = rec;
    rec.onstart = () => { timingRef.current.record_start_ms = nowMs(); };
    rec.ondataavailable = (e) => { if (!discardRef.current) uploader.add(e.data); };
    rec.onstop = async () => {
      stopMeter();
      if (timerRef.current) clearInterval(timerRef.current);
      if (discardRef.current) return;
      timingRef.current.record_stop_ms = nowMs();
      await finishUpload(uploader, rec.mimeType || "audio/webm");
    };
    rec.start(3000);  // a chunk every 3 s, uploaded while the student is still speaking
    startMeter(stream, (l) => {
      if (l > 0.18 && !timingRef.current.speech_start_ms) timingRef.current.speech_start_ms = nowMs();
    });
    setSecondsLeft(st.config.response_window_seconds);
    setPhase("recording");
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setSecondsLeft((x) => {
        if (x <= 1) { stopRecording(); return 0; }
        return x - 1;
      });
    }, 1000);
  };

  const finishUpload = async (uploader: ChunkUploader, mime: string) => {
    setPhase("uploading");
    setError("");
    const t = timingRef.current;
    const duration = t.record_start_ms && t.record_stop_ms ? (t.record_stop_ms - t.record_start_ms) / 1000 : null;
    try {
      await uploader.finish(mime, duration, t);
      await loadState();
      setPhase("done");
    } catch (e) {
      setError(`${(e as Error).message}`);
      setPhase("uploading");
    }
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

  const retryUpload = () => {
    if (uploaderRef.current) finishUpload(uploaderRef.current, recRef.current?.mimeType || "audio/webm");
  };

  // ---------------------------------------------------------------- navigation
  const nextPos = (p: Pos): Pos | null => {
    if (!st) return null;
    if (p.s + 1 < st.dialogues[p.d].segments.length) return { d: p.d, s: p.s + 1 };
    if (p.d + 1 < st.dialogues.length) return { d: p.d + 1, s: 0 };
    return null;
  };

  const goNext = () => {
    if (!pos) return;
    const n = nextPos(pos);
    setPhase("ready");
    setError("");
    if (n) setPos(n); else setStep("summary");
  };

  const skip = async () => {
    if (!cur || !confirm("Skip this segment? You will not be able to come back to it.")) return;
    try {
      await api(`/attempts/${id}/segments/${cur.segment_attempt_id}/skip`, { method: "POST" });
      await loadState();
      goNext();
    } catch (e) { setError((e as Error).message); }
  };

  const submit = async () => {
    setBusy(true);
    try {
      await api(`/attempts/${id}/submit`, { method: "POST" });
      streamRef.current?.getTracks().forEach((t) => t.stop());
      setStepState("submitted");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setStepState("submitted"); else setError((e as Error).message);
    }
    setBusy(false);
  };

  // ---------------------------------------------------------------- render
  if (fatal) return <div className="mx-auto max-w-lg p-8"><ErrorNote>{fatal}</ErrorNote></div>;
  if (!st) return <Spinner label="Loading test" />;

  const allSegs = st.dialogues.flatMap((d) => d.segments);
  const answered = allSegs.filter((s) => s.answered).length;
  const skipped = allSegs.filter((s) => s.skipped).length;
  const playsLeft = cur ? st.config.max_plays - cur.play_count : 0;
  const remaining = allSegs.some((s) => !s.answered && !s.skipped);
  const finished = !!cur && (cur.answered || cur.skipped);

  return (
    <div className="flex min-h-screen flex-col bg-slate-100" onContextMenu={(e) => e.preventDefault()}>
      {/* Hidden, control-less audio element: no seek bar, no download menu. */}
      <audio ref={audioRef} onEnded={onEnded} controls={false} controlsList="nodownload noplaybackrate" className="hidden"
        onTimeUpdate={(e) => setProgress({ t: e.currentTarget.currentTime, d: e.currentTarget.duration || 0 })} />

      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
        <Logo compact />
        <div className="truncate px-3 text-sm font-medium">{st.title}</div>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Badge tone={st.kind === "mock" ? "violet" : "brand"}>{st.kind === "mock" ? "Mock test" : "Practice"}</Badge>
          <span className="hidden tabular-nums sm:inline">{answered}/{allSegs.length} answered</span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        {step === "info1" && (
          <Card className="mx-auto max-w-2xl p-8">
            <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Information 1</div>
            <h1 className="mt-2 text-2xl font-semibold">About this {st.kind === "mock" ? "test" : "practice dialogue"}</h1>
            <p className="mt-4 text-slate-700">{st.kind === "mock" ? st.config.information_1 : st.config.information_1_practice}</p>
            <ul className="mt-6 space-y-2 text-sm">
              {st.dialogues.map((d) => <li key={d.dialogue_attempt_id} className="flex justify-between rounded-lg bg-slate-50 px-4 py-2"><span>Dialogue {d.position}: {d.title}</span><span className="text-slate-500">{d.segments.length} segments</span></li>)}
            </ul>
            <ul className="mt-6 list-disc space-y-1 pl-5 text-sm text-slate-600">
              <li>Each segment can be played {st.config.max_plays === 1 ? "once" : `up to ${st.config.max_plays} times (repeats are recorded)`}.</li>
              <li>Recording starts automatically after the chime and stops after {st.config.response_window_seconds} seconds, or when you press Finish Attempt.</li>
              <li>Your progress is saved. If you are disconnected, open the test again to continue.</li>
            </ul>
            <div className="mt-8 text-right"><Button size="lg" onClick={() => setStep("info2")}>Next</Button></div>
          </Card>
        )}

        {step === "info2" && (
          <Card className="mx-auto max-w-2xl p-8">
            <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Information 2 · Equipment check</div>
            <h1 className="mt-2 text-2xl font-semibold">Check your audio and microphone</h1>
            <p className="mt-4 text-slate-700">{st.config.information_2}</p>
            <div className="mt-6 space-y-4">
              <div className="flex items-center justify-between rounded-xl border border-slate-200 p-4">
                <div><div className="font-medium">1. Test sound</div><div className="text-sm text-slate-500">You should hear three tones.</div></div>
                <div className="flex items-center gap-2">
                  {soundOk && <Badge tone="green"><CheckCircle2 className="size-3" /> Heard</Badge>}
                  <Button variant="secondary" onClick={async () => { await playTestSound(); setSoundOk(true); }}><Volume2 className="size-4" /> Play test sound</Button>
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <div><div className="font-medium">2. Microphone</div>
                    <div className="text-sm text-slate-500">{mic === "recording" ? "Say a few words… recording 4 seconds" : mic === "playback" ? "Playing back your recording" : mic === "ok" ? "Your microphone works." : "Record a short sample and listen to it."}</div></div>
                  {mic === "ok" ? <Badge tone="green"><CheckCircle2 className="size-3" /> Ready</Badge>
                    : <Button variant="secondary" onClick={micCheck} loading={mic === "recording" || mic === "playback"}><Mic className="size-4" /> Record and play back</Button>}
                </div>
                {mic === "recording" && <LevelMeter level={level} />}
                {mic === "denied" && <div className="mt-3 flex gap-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-700"><MicOff className="size-4 shrink-0" /> Microphone access is blocked. Click the lock icon in the address bar, allow the microphone, then reload this page.</div>}
                {mic === "ok" && <button onClick={micCheck} className="mt-2 text-xs text-brand-600 hover:underline">Test again</button>}
              </div>
            </div>
            <div className="mt-8 flex justify-between">
              <Button variant="ghost" onClick={() => setStep("info1")}>Back</Button>
              <Button size="lg" disabled={mic !== "ok"} onClick={() => setStep(pos ? "segment" : "summary")}>{st.step === "segment" ? "Resume test" : "Start test"}</Button>
            </div>
          </Card>
        )}

        {step === "segment" && cur && curDlg && pos && (
          <>
            <SegmentStrip st={st} pos={pos} />
            <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_1.5fr]">
              <Card className="p-6">
                <div className="text-xs font-semibold uppercase tracking-wide text-brand-600">Dialogue {curDlg.position}{curDlg.topic ? ` · ${curDlg.topic}` : ""}</div>
                <h2 className="mt-1 text-lg font-semibold">{curDlg.title}</h2>
                {curDlg.description && <p className="mt-2 text-sm text-slate-600">{curDlg.description}</p>}
                <div className="mt-5 rounded-lg bg-brand-50 p-4 text-sm text-brand-900">
                  <div className="font-semibold">Segment {cur.number} of {curDlg.segments.length}</div>
                  <div className="mt-1">Interpret from <b>{cur.source_language}</b> into <b>{cur.target_language}</b>.</div>
                  {cur.speaker_role && <div className="mt-1 text-brand-900/80">Speaker: {cur.speaker_role}</div>}
                </div>
                <ol className="mt-5 list-decimal space-y-2 pl-5 text-sm text-slate-600">
                  <li>Press <b>Start</b> to hear the segment.</li>
                  <li>After the chime, recording starts automatically. Interpret the segment.</li>
                  <li>Press <b>Finish Attempt</b> when you have finished speaking.</li>
                </ol>
                {curDlg.instructions && <p className="mt-4 whitespace-pre-line text-sm text-slate-600">{curDlg.instructions}</p>}
              </Card>

              <Card className="p-6">
                {cur.has_waveform && (
                  <div className="relative overflow-hidden rounded-lg bg-slate-50">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`/api/attempts/${id}/segments/${cur.segment_attempt_id}/waveform`} alt="" className="h-20 w-full object-fill" draggable={false} />
                    {phase === "playing" && progress.d > 0 && <div className="absolute inset-y-0 w-0.5 bg-rose-500" style={{ left: `${(progress.t / progress.d) * 100}%` }} />}
                  </div>
                )}
                <div className="mt-4 flex items-center gap-3">
                  <Headphones className={cx("size-5", phase === "playing" ? "text-brand-600" : "text-slate-400")} />
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200" aria-label="Source audio progress">
                    <div className="h-full bg-brand-500 transition-[width] duration-300" style={{ width: progress.d ? `${(progress.t / progress.d) * 100}%` : "0%" }} />
                  </div>
                  <span className="w-10 text-right text-xs tabular-nums text-slate-500">{progress.t.toFixed(0)}s</span>
                </div>

                <div className="mt-6 rounded-xl border border-slate-200 p-5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">Your answer</span>
                    <span className="text-slate-500">Plays {cur.play_count}/{st.config.max_plays} · Recording {cur.record_count}/{st.config.max_record_attempts}</span>
                  </div>
                  <div className="mt-4 flex min-h-24 flex-col items-center justify-center">
                    {phase === "ready" && !finished && <p className="text-sm text-slate-500">{cur.play_count > 0 ? "You have already heard this segment." : "Press Start when you are ready."}</p>}
                    {phase === "loading" && <Loader2 className="size-6 animate-spin text-slate-400" />}
                    {phase === "playing" && <p className="text-sm font-medium text-brand-700">Listen… recording starts after the chime.</p>}
                    {phase === "recording" && (
                      <>
                        <div className="flex items-center gap-2 text-rose-600"><span className="size-2.5 animate-pulse rounded-full bg-rose-500" /> Recording · <span className={cx("tabular-nums", secondsLeft <= 5 && "font-semibold")}>{secondsLeft}s left</span></div>
                        <div className="mt-3 w-full max-w-sm"><LevelMeter level={level} /></div>
                      </>
                    )}
                    {phase === "uploading" && (error
                      ? <div className="text-center"><p className="text-sm text-rose-700">{error}</p><Button size="sm" className="mt-3" onClick={retryUpload}>Retry saving</Button></div>
                      : <p className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="size-4 animate-spin" /> Saving your answer…</p>)}
                    {(phase === "done" || cur.answered) && phase !== "uploading" && <p className="flex items-center gap-2 text-sm font-medium text-emerald-700"><CheckCircle2 className="size-5" /> Answer saved</p>}
                    {cur.skipped && <p className="text-sm text-slate-500">You skipped this segment.</p>}
                  </div>
                  <div className="mt-4 flex flex-wrap justify-center gap-3">
                    {!finished && phase === "ready" && playsLeft > 0 && (
                      <Button size="lg" onClick={play}><Play className="size-4" /> {cur.play_count > 0 ? "Play again" : "Start"}</Button>
                    )}
                    {!finished && phase === "ready" && cur.play_count > 0 && (
                      <Button size="lg" variant="secondary" onClick={startRecording}><Mic className="size-4" /> Record answer</Button>
                    )}
                    {phase === "recording" && <Button size="lg" onClick={stopRecording}><Square className="size-4" /> Finish Attempt</Button>}
                    {phase === "recording" && playsLeft > 0 && <Button size="lg" variant="secondary" onClick={repeat}><Repeat className="size-4" /> Repeat segment</Button>}
                  </div>
                </div>
                {error && phase !== "uploading" && <div className="mt-4"><ErrorNote>{error}</ErrorNote></div>}
                <div className="mt-6 flex items-center justify-between">
                  {!finished && phase === "ready" ? <Button variant="ghost" onClick={skip}><SkipForward className="size-4" /> Skip segment</Button> : <span />}
                  {finished && phase !== "uploading" && <Button onClick={goNext}>{nextPos(pos) ? "Next segment" : "Review and submit"}</Button>}
                </div>
              </Card>
            </div>
          </>
        )}

        {step === "segment" && !cur && (
          <Card className="mx-auto max-w-lg p-8 text-center"><p>All segments are done.</p><Button className="mt-4" onClick={() => setStep("summary")}>Review and submit</Button></Card>
        )}

        {step === "summary" && (
          <Card className="mx-auto max-w-2xl p-8">
            <h1 className="text-2xl font-semibold">Review before you submit</h1>
            <p className="mt-2 text-sm text-slate-600">{answered} answered, {skipped} skipped{allSegs.length - answered - skipped > 0 ? `, ${allSegs.length - answered - skipped} not attempted (these count as skipped)` : ""}.</p>
            {st.dialogues.map((d) => (
              <div key={d.dialogue_attempt_id} className="mt-6">
                <div className="text-sm font-semibold">Dialogue {d.position}: {d.title}</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {d.segments.map((s) => (
                    <span key={s.segment_attempt_id} title={s.answered ? "Answered" : s.skipped ? "Skipped" : "Not attempted"}
                      className={cx("flex size-8 items-center justify-center rounded text-xs font-medium tabular-nums",
                        s.answered ? "bg-emerald-100 text-emerald-800" : s.skipped ? "bg-rose-100 text-rose-700" : "bg-slate-100 text-slate-500")}>{s.number}</span>
                  ))}
                </div>
              </div>
            ))}
            {error && <div className="mt-6"><ErrorNote>{error}</ErrorNote></div>}
            <div className="mt-8 flex justify-between">
              {remaining && pos ? <Button variant="ghost" onClick={() => setStep("segment")}>Back to the test</Button> : <span />}
              <Button size="lg" loading={busy} onClick={() => { if (confirm("Submit now? You cannot change your answers after submitting.")) submit(); }}>Submit</Button>
            </div>
          </Card>
        )}

        {step === "submitted" && (
          <Card className="mx-auto max-w-lg p-10 text-center">
            <CheckCircle2 className="mx-auto size-10 text-emerald-600" />
            <h1 className="mt-4 text-xl font-semibold">Submitted</h1>
            <p className="mt-2 text-sm text-slate-600">We are transcribing and scoring your answers. This usually takes a few minutes; we will email you when your results are ready.</p>
            <div className="mt-6 flex justify-center gap-3">
              <Link href={`/results/${id}`} className="inline-flex h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700">View results</Link>
              <Link href="/dashboard" className="inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100">Dashboard</Link>
            </div>
          </Card>
        )}
      </main>
    </div>
  );
}

function SegmentStrip({ st, pos }: { st: State; pos: Pos }) {
  return (
    <div className="space-y-2">
      {st.dialogues.map((d, di) => (
        <div key={d.dialogue_attempt_id} className="flex items-center gap-3">
          <span className={cx("w-24 shrink-0 text-xs", di === pos.d ? "font-semibold text-ink" : "text-slate-400")}>Dialogue {d.position}</span>
          <div className="flex flex-1 gap-1">
            {d.segments.map((s, si) => (
              <div key={s.segment_attempt_id} className={cx("h-1.5 flex-1 rounded-full",
                di === pos.d && si === pos.s ? "bg-amber-400" : s.answered ? "bg-brand-500" : s.skipped ? "bg-rose-300" : "bg-slate-300/70")} />
            ))}
          </div>
        </div>
      ))}
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
