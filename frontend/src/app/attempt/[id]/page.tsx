"use client";

/**
 * The test player. Mirrors the NAATI CCL online test: Information 1, Information 2 (an example segment that checks
 * speakers, microphone and camera), one page per segment, then a summary. On a segment page the student clicks
 * Start, hears the segment, speaks after the chime and clicks Finish attempt. Clicking Start again repeats the
 * segment (limited per dialogue); only the last attempt's recording is kept and scored.
 */
import Hls from "hls.js";
import { Camera, CheckCircle2, Loader2, Lock, Mic, MicOff, Play } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { type ReactNode, type RefObject, useCallback, useEffect, useRef, useState } from "react";

import { ExamFrame, FinishButton, type FooterCell, InlineBtn, MicWave, mmss, RecBadge, SourceWave, StartButton, WebcamBox } from "@/components/exam";
import { Button, Card, cx, ErrorNote, Modal, Spinner } from "@/components/ui";
import { api, ApiError, type User } from "@/lib/api";
import { ChunkUploader, pickMime, playTestSound } from "@/lib/recorder";

type Seg = {
  segment_attempt_id: string; number: number; direction: string; source_language: string; target_language: string;
  speaker_role: string; attempts: number; record_count: number; answered: boolean; skipped: boolean; has_waveform: boolean;
};
type Dlg = {
  dialogue_attempt_id: string; position: number; title: string; description: string; instructions: string;
  topic: string | null; lote: string; repeats_used: number; segments: Seg[];
};
type State = {
  id: string; kind: "mock" | "practice"; title: string; status: string; step: string;
  current: { dialogue_attempt_id: string; segment_attempt_id: string } | null;
  config: {
    max_repeats_per_dialogue: number; response_window_seconds: number; chime_seconds: number;
    camera: { preview?: boolean; required?: boolean; example_record_seconds?: number };
    information_1: string; information_1_practice: string; information_2: string; max_upload_mb: number;
  };
  dialogues: Dlg[];
};
type Page = { kind: "info1" } | { kind: "info2" } | { kind: "segment"; d: number; s: number } | { kind: "summary" };
type Phase = "idle" | "loading" | "playing" | "recording" | "uploading";

const SAMPLE_MS = 50; // one mic-level sample every 50 ms for the live trace

/** Why the camera could not start, in words a student can act on. */
function cameraProblem(e: unknown): string {
  const err = e as DOMException;
  if (err?.name === "NotReadableError" || err?.name === "TrackStartError" || err?.name === "AbortError") {
    return "The camera is being used by another app or tab (for example Zoom, Teams or the Camera app). Close it, then try again.";
  }
  if (err?.name === "NotFoundError" || err?.name === "DevicesNotFoundError") return "No camera was found on this device.";
  if (err?.name === "NotAllowedError" && /system/i.test(err.message || "")) {
    return "Your computer is blocking the camera. In Windows: Settings > Privacy & security > Camera, turn on camera access for apps and desktop apps.";
  }
  if (err?.name === "NotAllowedError") return "The camera is blocked for this site. Allow it from the lock icon in the address bar.";
  return "The camera could not start. Try again, or continue without it.";
}
const nowMs = () => Date.now();

function buildPages(st: State): Page[] {
  const segs: Page[] = st.dialogues.flatMap((d, di) => d.segments.map((_, si) => ({ kind: "segment" as const, d: di, s: si })));
  return [{ kind: "info1" }, { kind: "info2" }, ...segs, { kind: "summary" }];
}

export default function Player() {
  const { id } = useParams<{ id: string }>();
  const [st, setSt] = useState<State | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [idx, setIdx] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [fatal, setFatal] = useState("");
  const [help, setHelp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);         // source playback 0..1
  const [elapsed, setElapsed] = useState(0);           // seconds recorded
  const [tick, setTick] = useState(0);                 // redraws the mic trace
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [deviceError, setDeviceError] = useState("");
  const [cameraIssue, setCameraIssue] = useState("");  // why the camera is off, in plain words
  const cameraOffByUser = useRef(false);  // the student switched the camera off: do not turn it back on by itself
  // Camera and microphone permission prompt: shown on the equipment check until the browser has granted access.
  const [devicePrompt, setDevicePrompt] = useState<null | "ask" | "denied" | "nodevice">(null);
  const [asking, setAsking] = useState(false);
  // Information 2 example segment
  const [example, setExample] = useState<{ attempts: number; blob: Blob | null; heard: boolean; playing: boolean }>({ attempts: 0, blob: null, heard: false, playing: false });

  const audioRef = useRef<HTMLAudioElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const uploaderRef = useRef<ChunkUploader | null>(null);
  const timingRef = useRef<Record<string, number>>({});
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const meterRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const samplesRef = useRef<number[]>([]);
  const phaseRef = useRef<Phase>("idle");
  useEffect(() => { phaseRef.current = phase; }, [phase]);

  const loadState = useCallback(async () => {
    const s = await api<State>(`/attempts/${id}/state`);
    setSt(s);
    return s;
  }, [id]);

  // ---------------------------------------------------------------- boot / resume
  useEffect(() => {
    api<User>("/me").then(setMe).catch(() => {});
    api<State>(`/attempts/${id}/state`).then((s) => {
      setSt(s);
      if (s.status !== "In Progress") { setSubmitted(true); return; }
      // After a reload the equipment check runs again (the browser asks for the microphone again).
      setIdx(s.step === "info1" ? 0 : 1);
      if (s.step !== "info1") api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "reload", detail: s.step } }).catch(() => {});
    }).catch((e) => setFatal(e.message));
    return () => {
      hlsRef.current?.destroy();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (timerRef.current) clearInterval(timerRef.current);
      if (meterRef.current) clearInterval(meterRef.current);
      ctxRef.current?.close().catch(() => {});
    };
  }, [id]);

  useEffect(() => {
    const onVis = () => {
      if (document.hidden && ["playing", "recording"].includes(phaseRef.current)) {
        api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "tab_blur" } }).catch(() => {});
      }
    };
    const onLeave = (e: BeforeUnloadEvent) => { if (["playing", "recording", "uploading"].includes(phaseRef.current)) e.preventDefault(); };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("beforeunload", onLeave);
    return () => { document.removeEventListener("visibilitychange", onVis); window.removeEventListener("beforeunload", onLeave); };
  }, [id]);

  const pages = st ? buildPages(st) : [];
  const page = pages[idx];
  const cur = st && page?.kind === "segment" ? st.dialogues[page.d].segments[page.s] : null;
  const curDlg = st && page?.kind === "segment" ? st.dialogues[page.d] : null;

  const goTo = (i: number) => {
    if (!st || i < 0 || i >= pages.length) return;
    setIdx(i);
    setError("");
    setProgress(0);
    samplesRef.current = [];
    setTick((t) => t + 1);
    const p = pages[i];
    api(`/attempts/${id}/step`, { method: "POST", json: { step: p.kind } }).catch(() => {});
  };

  // ---------------------------------------------------------------- devices: microphone (+ camera preview)
  const getDevices = async () => {
    if (streamRef.current) return streamRef.current;
    const wantCamera = st?.config.camera?.preview !== false;
    let s: MediaStream;
    try {
      s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: wantCamera });
      setCameraIssue("");
    } catch (e) {
      if (!wantCamera) throw e;
      setCameraIssue(cameraProblem(e));
      // No camera (or camera refused): carry on with the microphone only, unless the camera is required.
      s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      if (st?.config.camera?.required) setDeviceError("A camera is required for this test. Allow the camera and reload.");
      api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "camera_unavailable", detail: (e as DOMException)?.name } }).catch(() => {});
    }
    streamRef.current = s;
    setStream(s);
    return s;
  };

  /** Ask the browser for camera + microphone (the browser shows its own permission request). */
  const requestDevices = async () => {
    setAsking(true);
    try {
      await getDevices();
      setDevicePrompt(null);
    } catch (e) {
      const name = (e as DOMException)?.name;
      setDevicePrompt(name === "NotFoundError" || name === "OverconstrainedError" ? "nodevice" : "denied");
      api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "mic_denied", detail: name } }).catch(() => {});
    } finally {
      setAsking(false);
    }
  };

  const needsDevices = page?.kind === "info2" || page?.kind === "segment";
  useEffect(() => {
    if (!needsDevices || streamRef.current || submitted) return;
    let cancelled = false;
    (async () => {
      let state: "granted" | "denied" | "prompt" = "prompt";
      try {
        const names = (st?.config.camera?.preview !== false ? ["microphone", "camera"] : ["microphone"]) as PermissionName[];
        const results = await Promise.all(names.map((n) => navigator.permissions.query({ name: n })));
        state = results.some((r) => r.state === "denied") ? "denied" : results.every((r) => r.state === "granted") ? "granted" : "prompt";
      } catch { /* Permissions API not available for camera/mic in this browser: just ask */ }
      if (cancelled) return;
      if (state === "granted") requestDevices();
      else setDevicePrompt(state === "denied" ? "denied" : "ask");
    })();
    return () => { cancelled = true; };
  }, [needsDevices, submitted]); // eslint-disable-line react-hooks/exhaustive-deps

  /** After the student changes the browser's camera / microphone setting (or comes back to the tab), turn the camera
   * and microphone on straight away, without a reload. Never while the segment is playing or being recorded. */
  const refreshDevices = async (manual = false) => {
    if ((!needsDevices && !manual) || submitted || phaseRef.current !== "idle") return;
    if (cameraOffByUser.current && !manual) return;
    cameraOffByUser.current = false;
    const current = streamRef.current;
    if (!current) { await requestDevices(); return; }
    const wantCamera = st?.config.camera?.preview !== false;
    if (!wantCamera || current.getVideoTracks().some((t) => t.readyState === "live")) return;
    try {
      // Free the old tracks first: some cameras/drivers refuse a second open while the microphone stream is held.
      current.getTracks().forEach((t) => t.stop());
      let s: MediaStream;
      try {
        s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: true });
        setCameraIssue("");
      } catch (e) {
        if (manual) setCameraIssue(cameraProblem(e));
        s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      }
      streamRef.current = s;
      setStream(s);
      setDeviceError("");
      setDevicePrompt(null);
    } catch { /* microphone lost too: the next Start asks again */ }
  };

  /** Camera off, microphone untouched (safe while recording). */
  const turnCameraOff = () => {
    const current = streamRef.current;
    if (!current) return;
    cameraOffByUser.current = true;
    current.getVideoTracks().forEach((t) => t.stop());
    const audioOnly = new MediaStream(current.getAudioTracks());
    streamRef.current = audioOnly;
    setStream(audioOnly);
    setCameraIssue("You turned the camera off.");
  };

  useEffect(() => {
    if (!needsDevices || submitted) return;
    const statuses: PermissionStatus[] = [];
    const onChange = () => { refreshDevices(); };
    (async () => {
      try {
        for (const name of ["camera", "microphone"] as PermissionName[]) {
          const status = await navigator.permissions.query({ name });
          status.addEventListener("change", onChange);
          statuses.push(status);
        }
      } catch { /* no Permissions API for camera/mic here: the focus check below still works */ }
    })();
    const onFocus = () => { if (!document.hidden) refreshDevices(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    return () => {
      statuses.forEach((status) => status.removeEventListener("change", onChange));
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, [needsDevices, submitted]); // eslint-disable-line react-hooks/exhaustive-deps

  const startMeter = (s: MediaStream, onLevel?: (l: number) => void) => {
    ctxRef.current?.close().catch(() => {});
    const ctx = new AudioContext();
    ctxRef.current = ctx;
    const an = ctx.createAnalyser();
    an.fftSize = 1024;
    ctx.createMediaStreamSource(new MediaStream(s.getAudioTracks())).connect(an);
    const buf = new Uint8Array(an.fftSize);
    samplesRef.current = [];
    if (meterRef.current) clearInterval(meterRef.current);
    meterRef.current = setInterval(() => {
      an.getByteTimeDomainData(buf);
      let peak = 0;
      for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
      const l = Math.min(1, peak / 64);
      samplesRef.current.push(l);
      onLevel?.(l);
      setTick((t) => t + 1);
    }, SAMPLE_MS);
  };
  const stopMeter = () => { if (meterRef.current) clearInterval(meterRef.current); meterRef.current = null; };

  const startTimer = (limit: number, onLimit: () => void) => {
    setElapsed(0);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setElapsed((x) => {
        if (x + 1 >= limit) { onLimit(); return limit; }
        return x + 1;
      });
    }, 1000);
  };
  const stopTimer = () => { if (timerRef.current) clearInterval(timerRef.current); timerRef.current = null; };

  // ---------------------------------------------------------------- Information 2: example segment
  const exampleStart = async () => {
    setError("");
    let s: MediaStream;
    try { s = await getDevices(); } catch {
      await requestDevices();
      return;
    }
    setExample((e) => ({ ...e, attempts: e.attempts + 1, blob: null }));
    setPhase("playing");
    setProgress(0);
    const t0 = nowMs();
    const anim = setInterval(() => setProgress(Math.min(1, (nowMs() - t0) / 1600)), 100);
    await playTestSound();
    clearInterval(anim);
    setProgress(1);
    const mime = pickMime();
    const rec = new MediaRecorder(new MediaStream(s.getAudioTracks()), mime ? { mimeType: mime } : undefined);
    recRef.current = rec;
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      stopMeter();
      stopTimer();
      setExample((e) => ({ ...e, blob: new Blob(chunks, { type: rec.mimeType }) }));
      setPhase("idle");
    };
    rec.start();
    startMeter(s);
    setPhase("recording");
    startTimer(st?.config.camera?.example_record_seconds ?? 10, () => rec.state !== "inactive" && rec.stop());
  };

  const examplePlay = () => {
    if (!example.blob) return;
    const a = new Audio(URL.createObjectURL(example.blob));
    setExample((e) => ({ ...e, playing: true }));
    a.onended = () => setExample((e) => ({ ...e, playing: false, heard: true }));
    a.play().catch(() => setExample((e) => ({ ...e, playing: false, heard: true })));
  };

  // ---------------------------------------------------------------- segment attempt: Start -> listen -> chime -> record -> Finish attempt
  const start = async () => {
    if (!cur || !curDlg || !st) return;
    if (cur.attempts > 0 && !confirm(`Repeat segment ${cur.number}? This uses your segment repeat for this dialogue, and only your new attempt will be kept.`)) return;
    setError("");
    try { await getDevices(); } catch { await requestDevices(); return; }
    setPhase("loading");
    let url: string;
    try {
      url = (await api<{ url: string }>(`/attempts/${id}/segments/${cur.segment_attempt_id}/play`, { method: "POST" })).url;
    } catch (e) {
      setError((e as Error).message);
      setPhase("idle");
      await loadState();
      return;
    }
    await loadState();
    samplesRef.current = [];
    setTick((t) => t + 1);
    setProgress(0);
    const audio = audioRef.current!;
    hlsRef.current?.destroy();
    const failed = (msg: string) => { setError(msg); setPhase("idle"); };
    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true });
      hlsRef.current = hls;
      hls.on(Hls.Events.MANIFEST_PARSED, () => { audio.play().then(() => setPhase("playing")).catch(() => failed("Your browser blocked the audio. Click Start again.")); });
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data.fatal) {
          failed("The audio could not be played. Check your connection and click Start again.");
          api(`/attempts/${id}/integrity`, { method: "POST", json: { type: "audio_error", detail: data.details } }).catch(() => {});
        }
      });
      hls.loadSource(url);
      hls.attachMedia(audio);
    } else if (audio.canPlayType("application/vnd.apple.mpegurl")) {
      audio.src = url;
      audio.play().then(() => setPhase("playing")).catch(() => failed("Click Start again to allow audio."));
    } else {
      failed("This browser cannot play the test audio. Please use a recent Chrome, Edge, Firefox or Safari.");
    }
  };

  const onEnded = () => {
    if (phaseRef.current !== "playing") return;
    hlsRef.current?.destroy();
    hlsRef.current = null;
    timingRef.current = { chime_end_ms: nowMs() };  // the chime is the last thing in the segment audio
    startRecording();
  };

  const startRecording = async () => {
    if (!st || !cur) return;
    const s = streamRef.current ?? await getDevices();
    const uploader = new ChunkUploader(`/attempts/${id}/segments/${cur.segment_attempt_id}/recording`);
    uploaderRef.current = uploader;
    const mime = pickMime();
    const rec = new MediaRecorder(new MediaStream(s.getAudioTracks()), mime ? { mimeType: mime } : undefined);
    recRef.current = rec;
    rec.onstart = () => { timingRef.current.record_start_ms = nowMs(); };
    rec.ondataavailable = (e) => uploader.add(e.data);
    rec.onstop = async () => {
      stopMeter();
      stopTimer();
      timingRef.current.record_stop_ms = nowMs();
      await finishUpload(uploader, rec.mimeType || "audio/webm");
    };
    rec.start(3000);  // a chunk every 3 s, uploaded while the student is still speaking
    startMeter(s, (l) => { if (l > 0.18 && !timingRef.current.speech_start_ms) timingRef.current.speech_start_ms = nowMs(); });
    setPhase("recording");
    startTimer(st.config.response_window_seconds, () => finishAttempt());
  };

  const finishAttempt = () => {
    if (recRef.current && recRef.current.state !== "inactive") recRef.current.stop();
  };

  const finishUpload = async (uploader: ChunkUploader, mime: string) => {
    setPhase("uploading");
    setError("");
    const t = timingRef.current;
    const duration = t.record_start_ms && t.record_stop_ms ? (t.record_stop_ms - t.record_start_ms) / 1000 : null;
    try {
      await uploader.finish(mime, duration, t);
      await loadState();
      setPhase("idle");
    } catch (e) {
      setError(`${(e as Error).message}`);
    }
  };

  const retryUpload = () => { if (uploaderRef.current) finishUpload(uploaderRef.current, recRef.current?.mimeType || "audio/webm"); };

  const submit = async () => {
    setBusy(true);
    try {
      await api(`/attempts/${id}/submit`, { method: "POST" });
      streamRef.current?.getTracks().forEach((t) => t.stop());
      setSubmitted(true);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setSubmitted(true); else setError((e as Error).message);
    }
    setBusy(false);
  };

  // ---------------------------------------------------------------- render
  if (fatal) return <div className="mx-auto max-w-lg p-8"><ErrorNote>{fatal}</ErrorNote></div>;
  if (!st) return <Spinner label="Loading test" />;

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <Card className="max-w-lg p-10 text-center">
          <CheckCircle2 className="mx-auto size-10 text-emerald-600" />
          <h1 className="mt-4 text-xl font-semibold">Submitted</h1>
          <p className="mt-2 text-sm text-slate-600">We are transcribing and scoring your answers. This usually takes a few minutes; we will email you when your results are ready.</p>
          <div className="mt-6 flex justify-center gap-3">
            <Link href={`/results/${id}`} className="inline-flex h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700">View results</Link>
            <Link href="/dashboard" className="inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium text-slate-600 hover:bg-slate-100">Dashboard</Link>
          </div>
        </Card>
      </div>
    );
  }

  const allSegs = st.dialogues.flatMap((d) => d.segments);
  const answered = allSegs.filter((s) => s.answered).length;
  const locked = phase !== "idle";  // no navigation while listening, recording or saving
  const maxRepeats = st.config.max_repeats_per_dialogue;
  const canRepeat = !!curDlg && curDlg.repeats_used < maxRepeats;
  const canStart = !!cur && !cur.skipped && phase === "idle" && (cur.attempts === 0 || canRepeat);
  const exampleDone = example.blob !== null;

  const cells: FooterCell[] = pages.map((p, i) => {
    if (i === idx) return { state: "current" };
    if (p.kind === "segment") {
      const s = st.dialogues[p.d].segments[p.s];
      return { state: s.answered ? "done" : s.skipped ? "skipped" : "todo" };
    }
    return { state: i < idx ? "done" : "todo" };
  });
  const title = page.kind === "info1" ? "Information 1" : page.kind === "info2" ? "Information 2" : page.kind === "summary" ? "Summary"
    : `Segment ${cur!.number}`;
  const crumb = page.kind === "segment" ? `${st.title} | Dialogue ${curDlg!.position}` : `${st.title} | ${st.kind === "mock" ? "Mock test" : "Practice dialogue"}`;
  const repeatRule = maxRepeats === 0 ? "Segments cannot be repeated in this test."
    : `You may repeat ${maxRepeats === 1 ? "one segment" : `${maxRepeats} segments`} per dialogue without penalty.`;
  // From the example segment, go to the first unanswered segment (the start, or where a resumed test left off).
  const next = () => {
    if (page.kind !== "info2") return goTo(idx + 1);
    const at = st.current ? pages.findIndex((p) => p.kind === "segment" && st.dialogues[p.d].segments[p.s].segment_attempt_id === st.current!.segment_attempt_id) : -1;
    goTo(at >= 0 ? at : pages.length - 1);
  };
  const nextDisabled = locked || (page.kind === "info2" && (!exampleDone || (!!st.config.camera?.required && !stream?.getVideoTracks().length)));

  return (
    <>
      {/* Hidden, control-less audio element: no seek bar, no download menu. */}
      <audio ref={audioRef} onEnded={onEnded} controls={false} controlsList="nodownload noplaybackrate" className="hidden"
        onTimeUpdate={(e) => setProgress(e.currentTarget.duration ? e.currentTarget.currentTime / e.currentTarget.duration : 0)} />
      <ExamFrame user={me ? { name: me.name, email: me.email } : null} crumb={crumb} pageNo={idx + 1} pageCount={pages.length}
        title={title} onHelp={() => setHelp(true)} cells={cells}
        onPrev={idx > 0 ? () => goTo(idx - 1) : undefined} prevDisabled={locked}
        onNext={page.kind !== "summary" ? next : undefined} nextDisabled={nextDisabled}>

        {page.kind === "info1" && (
          <div className="max-w-3xl space-y-4">
            <h2 className="text-sm font-bold uppercase tracking-wide text-emerald-700">Information for candidates</h2>
            <p>{st.kind === "mock" ? st.config.information_1 : st.config.information_1_practice}</p>
            <ul className="space-y-1">
              {st.dialogues.map((d) => <li key={d.dialogue_attempt_id}>Dialogue {d.position}: <b>{d.title}</b> ({d.segments.length} segments, English and {d.lote})</li>)}
            </ul>
            <p>To repeat a segment, click <b>Finish attempt</b> and then the <b>Start</b> button again. {repeatRule} Only your last attempt is kept and scored.</p>
            <p>Recording starts automatically after the chime and stops after {st.config.response_window_seconds} seconds if you have not clicked Finish attempt.</p>
            <p>Your progress is saved. If you are disconnected, open the test again to continue.</p>
            <p className="pt-2">Please click <b>Next</b> to start with the <b>example segment</b>.</p>
          </div>
        )}

        {page.kind === "info2" && (
          <TwoColumns
            left={(
              <div className="space-y-4">
                <h2 className="text-sm font-bold uppercase tracking-wide text-emerald-700">Example segment</h2>
                <p>{st.config.information_2}</p>
                <ul className="list-disc space-y-1 pl-5">
                  <li>Click <InlineBtn>Start</InlineBtn> to hear the example and speak after it.</li>
                  <li>Click <InlineBtn outline>Finish attempt</InlineBtn> when you have finished.</li>
                  <li>Click <b>Play</b> to listen to your recording. (Play is only available on the example segment.)</li>
                </ul>
                <p className="font-semibold">Repeat</p>
                <p>{repeatRule} To repeat, click <InlineBtn>Start</InlineBtn> again.</p>
                {st.step !== "info1" && st.step !== "info2" && <p className="rounded bg-amber-50 p-3 text-sm text-amber-800">Welcome back. Check your equipment again, then click Next to continue where you left off.</p>}
              </div>
            )}
            right={(
              <MediaPanel stream={stream} cameraIssue={cameraIssue} onCameraRetry={stream ? () => refreshDevices(true) : undefined} onCameraOff={turnCameraOff} recording={phase === "recording"} progress={progress} waveformSrc={null}
                samplesRef={samplesRef} capacity={(st.config.camera?.example_record_seconds ?? 10) * 1000 / SAMPLE_MS} tick={tick}
                timeLabel={phase === "recording" ? `${mmss(elapsed)} / ${mmss(st.config.camera?.example_record_seconds ?? 10)}` : mmss(st.config.camera?.example_record_seconds ?? 10)}>
                <span className="text-sm text-slate-600">Attempts: {example.attempts}</span>
                <button onClick={examplePlay} disabled={!example.blob || phase !== "idle" || example.playing} aria-label="Play your recording"
                  className="inline-flex size-9 items-center justify-center rounded-full border border-slate-400 text-slate-700 disabled:border-slate-200 disabled:text-slate-300"><Play className="size-4" /></button>
                {phase === "recording" ? <><FinishButton onClick={() => recRef.current?.state !== "inactive" && recRef.current?.stop()} /><RecBadge /></>
                  : <StartButton onClick={exampleStart} disabled={phase !== "idle"} />}
              </MediaPanel>
            )}
            notes={<>
              {deviceError && <div className="flex gap-2 rounded bg-amber-50 p-3 text-sm text-amber-800"><MicOff className="size-4 shrink-0" /> {deviceError}</div>}
              {exampleDone && <p className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="size-4" /> Recording saved. Click Play to listen, then Next to begin.</p>}
              {!exampleDone && <p className="text-xs text-slate-500">Complete the example segment to continue.</p>}
            </>}
          />
        )}

        {page.kind === "segment" && cur && curDlg && (
          <TwoColumns
            left={(
              <div className="space-y-4">
                <h2 className="text-lg font-bold">{curDlg.lote} CCL test</h2>
                <p className="text-sm text-slate-600">Dialogue {curDlg.position}: {curDlg.title}{curDlg.topic ? ` · ${curDlg.topic}` : ""}</p>
                {curDlg.description && cur.number === 1 && <p className="text-sm text-slate-600">{curDlg.description}</p>}
                <div>
                  <p className="font-semibold">To hear the segment</p>
                  <ul className="mt-2 space-y-2 pl-1">
                    <li>• Click <InlineBtn>Start</InlineBtn> and speak after the chime</li>
                    <li>• Click <InlineBtn outline>Finish attempt</InlineBtn> to upload</li>
                  </ul>
                </div>
                {maxRepeats > 0 && (
                  <div>
                    <p className="font-semibold">To repeat a segment</p>
                    <p className="text-sm text-slate-600">({maxRepeats === 1 ? "One" : maxRepeats} per dialogue without penalty)</p>
                    <ul className="mt-2 pl-1"><li>• Click <InlineBtn>Start</InlineBtn> again</li></ul>
                    <p className="mt-2 text-xs text-slate-500">Repeats used in this dialogue: {curDlg.repeats_used} of {maxRepeats}</p>
                  </div>
                )}
                <p className="text-sm text-slate-600">Interpret into <b>{cur.target_language}</b>.</p>
                {curDlg.instructions && cur.number === 1 && <p className="whitespace-pre-line text-sm text-slate-600">{curDlg.instructions}</p>}
              </div>
            )}
            right={(
              <MediaPanel stream={stream} cameraIssue={cameraIssue} onCameraRetry={stream ? () => refreshDevices(true) : undefined} onCameraOff={turnCameraOff} recording={phase === "recording"} progress={phase === "playing" ? progress : phase === "recording" || phase === "uploading" ? 1 : 0}
                waveformSrc={cur.has_waveform ? `/api/attempts/${id}/segments/${cur.segment_attempt_id}/waveform` : null}
                samplesRef={samplesRef} capacity={(st.config.response_window_seconds * 1000) / SAMPLE_MS} tick={tick}
                timeLabel={phase === "recording" ? `${mmss(elapsed)} / ${mmss(st.config.response_window_seconds)}` : mmss(st.config.response_window_seconds)}>
                <span className="text-sm text-slate-600">Attempts: {cur.attempts}</span>
                {phase === "loading" && <Loader2 className="size-5 animate-spin text-slate-400" />}
                {(phase === "playing" || phase === "recording") && <FinishButton onClick={finishAttempt} disabled={phase !== "recording"} />}
                {phase === "recording" && <RecBadge />}
                {phase === "idle" && <StartButton onClick={start} disabled={!canStart} />}
              </MediaPanel>
            )}
            notes={<>
              {phase === "playing" && <p className="text-sm text-slate-600">Listen. Recording starts after the chime.</p>}
              {phase === "uploading" && (error
                ? <div className="text-sm"><p className="text-rose-700">{error}</p><Button size="sm" className="mt-2" onClick={retryUpload}>Retry saving</Button></div>
                : <p className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="size-4 animate-spin" /> Saving your answer…</p>)}
              {phase === "idle" && cur.answered && <p className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="size-4" /> Answer saved{cur.attempts > 1 ? " (your last attempt)" : ""}. Click Next to continue.</p>}
              {phase === "idle" && cur.attempts > 0 && !cur.answered && <p className="text-sm text-amber-700">This attempt was not saved.{canRepeat ? " Click Start to try again." : ""}</p>}
              {phase === "idle" && cur.attempts > 0 && !canRepeat && maxRepeats > 0 && <p className="text-xs text-slate-500">You have used the repeat for this dialogue.</p>}
              {deviceError && <p className="text-sm text-amber-700">{deviceError}</p>}
              {error && phase !== "uploading" && <ErrorNote>{error}</ErrorNote>}
            </>}
          />
        )}

        {page.kind === "summary" && (
          <div className="max-w-3xl">
            <p>{answered} of {allSegs.length} segments answered. Segments without an answer are marked as skipped when you submit.</p>
            {st.dialogues.map((d) => (
              <div key={d.dialogue_attempt_id} className="mt-6">
                <div className="text-sm font-semibold">Dialogue {d.position}: {d.title}</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {d.segments.map((s) => {
                    const at = pages.findIndex((p) => p.kind === "segment" && st.dialogues[p.d].segments[p.s].segment_attempt_id === s.segment_attempt_id);
                    return (
                      <button key={s.segment_attempt_id} onClick={() => goTo(at)} title={s.answered ? "Answered" : "Not answered: click to go to this segment"}
                        className={cx("flex size-9 items-center justify-center rounded text-xs font-medium tabular-nums",
                          s.answered ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-700 hover:bg-rose-200")}>{s.number}</button>
                    );
                  })}
                </div>
              </div>
            ))}
            <div className="mt-4 flex gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="size-3 rounded bg-emerald-100" /> Answered</span>
              <span className="flex items-center gap-1"><span className="size-3 rounded bg-rose-100" /> Skipped</span>
            </div>
            {error && <div className="mt-6"><ErrorNote>{error}</ErrorNote></div>}
            <div className="mt-8"><Button size="lg" loading={busy} onClick={() => { if (confirm("Submit now? You cannot change your answers after submitting.")) submit(); }}>Submit test</Button></div>
          </div>
        )}
      </ExamFrame>

      <Modal open={!!devicePrompt} onClose={() => setDevicePrompt(null)}
        title={devicePrompt === "denied" ? "Camera and microphone are blocked" : devicePrompt === "nodevice" ? "No microphone found" : "Allow camera and microphone"}>
        <div className="space-y-4 text-sm text-slate-700">
          <div className="flex justify-center gap-4 py-2">
            <span className="flex size-14 items-center justify-center rounded-full bg-brand-50 text-brand-700"><Mic className="size-6" /></span>
            {st.config.camera?.preview !== false && <span className="flex size-14 items-center justify-center rounded-full bg-brand-50 text-brand-700"><Camera className="size-6" /></span>}
          </div>
          {devicePrompt === "ask" && <>
            <p>This test records your interpretation, so it needs your <b>microphone</b>.{st.config.camera?.preview !== false && <> Your <b>camera</b> is shown on screen like in the real exam; the video is not recorded or uploaded.</>}</p>
            <p>Click the button below, then choose <b>Allow</b> when your browser asks.</p>
            <Button className="w-full" loading={asking} onClick={requestDevices}><Mic className="size-4" /> Allow camera and microphone</Button>
          </>}
          {devicePrompt === "denied" && <>
            <p>Your browser is blocking access, so it will not ask again until you change the setting:</p>
            <ol className="list-decimal space-y-1 pl-5">
              <li>Click the <Lock className="inline size-3.5" /> lock (or settings) icon at the left of the address bar.</li>
              <li>Set <b>Microphone</b>{st.config.camera?.preview !== false && <> and <b>Camera</b></>} to <b>Allow</b>.</li>
              <li>Click <b>Try again</b> below (or reload the page).</li>
            </ol>
            <div className="flex gap-2">
              <Button className="flex-1" loading={asking} onClick={requestDevices}>Try again</Button>
              <Button variant="secondary" onClick={() => window.location.reload()}>Reload page</Button>
            </div>
          </>}
          {devicePrompt === "nodevice" && <>
            <p>We could not find a microphone. Plug in a headset or microphone, check it is not used by another app, then try again.</p>
            <Button className="w-full" loading={asking} onClick={requestDevices}>Try again</Button>
          </>}
        </div>
      </Modal>

      <Modal open={help} onClose={() => setHelp(false)} title="Help">
        <div className="space-y-3 text-sm text-slate-700">
          <p><b>Answering a segment:</b> click Start, listen to the segment and speak after the chime. Click Finish attempt when you have finished. Recording stops by itself after {st.config.response_window_seconds} seconds.</p>
          <p><b>Repeating:</b> {repeatRule} Click Start again to repeat; only your last attempt is kept.</p>
          <p><b>Moving around:</b> use Previous and Next at the bottom right. You cannot move while the segment is playing or while you are recording.</p>
          <p><b>Camera:</b> your camera is shown so the test feels like the real exam. The video is not recorded or uploaded.</p>
          <p><b>Problems:</b> if your microphone or camera does not work, allow them in the browser&apos;s address bar and reload the page. Your answers so far are saved.</p>
        </div>
      </Modal>
    </>
  );
}

function TwoColumns({ left, right, notes }: { left: ReactNode; right: ReactNode; notes: ReactNode }) {
  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_1.15fr]">
      <div>{left}</div>
      <div className="space-y-3">{right}<div className="space-y-2">{notes}</div></div>
    </div>
  );
}

function MediaPanel({ stream, recording, progress, waveformSrc, samplesRef, capacity, tick, timeLabel, cameraIssue, onCameraRetry, onCameraOff, children }: {
  stream: MediaStream | null; recording: boolean; cameraIssue?: string; onCameraRetry?: () => void; onCameraOff?: () => void; progress: number; waveformSrc: string | null;
  samplesRef: RefObject<number[]>; capacity: number; tick: number; timeLabel: string; children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <WebcamBox stream={stream} recording={recording} issue={cameraIssue} onRetry={onCameraRetry} onTurnOff={onCameraOff} />
      <div className="pt-2"><SourceWave src={waveformSrc} progress={progress} /></div>
      <MicWave samplesRef={samplesRef} capacity={capacity} recording={recording} tick={tick} />
      <div className="ml-6 flex justify-between text-xs tabular-nums text-slate-500"><span>0:00</span><span>{timeLabel}</span></div>
      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">{children}</div>
    </div>
  );
}
