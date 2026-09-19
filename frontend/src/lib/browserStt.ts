// Browser speech recognition (Web Speech API), used as the STT fallback when
// the server has no Whisper key. Chrome/Edge only; runs alongside MediaRecorder
// on the live mic because it can't transcribe a recorded file.

type Alt = { transcript: string; confidence: number };
type Result = { isFinal: boolean; 0: Alt; length: number };
type ResultEvent = { resultIndex: number; results: { length: number; [i: number]: Result } };
type Recognition = {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: ResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  start: () => void; stop: () => void; abort: () => void;
};
type RecognitionCtor = new () => Recognition;

function ctor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const browserSttSupported = () => ctor() !== null;

export type BrowserTranscript = { text: string; confidence: number | null };

export class BrowserStt {
  private rec: Recognition | null = null;
  private finals: string[] = [];
  private confs: number[] = [];
  private interim = "";
  private active = false;
  private endResolve: (() => void) | null = null;

  constructor(private onUpdate?: (text: string) => void) {}

  start(locale: string) {
    const C = ctor();
    if (!C) return;
    this.finals = [];
    this.confs = [];
    this.interim = "";
    this.active = true;
    const rec = new C();
    rec.lang = locale;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) {
          this.finals.push(r[0].transcript.trim());
          if (r[0].confidence > 0) this.confs.push(r[0].confidence);
        } else interim += r[0].transcript;
      }
      this.interim = interim;
      this.onUpdate?.(this.text());
    };
    // Chrome ends recognition on silence; keep it alive for the whole answer.
    rec.onend = () => {
      if (this.active) { try { rec.start(); } catch {} }
      else this.endResolve?.();
    };
    rec.onerror = (e) => { if (e.error === "not-allowed" || e.error === "service-not-allowed") this.active = false; };
    this.rec = rec;
    try { rec.start(); } catch {}
  }

  private text() {
    return [...this.finals, this.interim.trim()].filter(Boolean).join(" ");
  }

  /** Stop and wait briefly for the last final result. */
  async stop(): Promise<BrowserTranscript> {
    if (!this.rec) return { text: "", confidence: null };
    this.active = false;
    const ended = new Promise<void>((r) => { this.endResolve = r; });
    try { this.rec.stop(); } catch {}
    await Promise.race([ended, new Promise((r) => setTimeout(r, 1200))]);
    this.rec = null;
    const confidence = this.confs.length ? this.confs.reduce((a, b) => a + b, 0) / this.confs.length : null;
    return { text: this.text(), confidence };
  }

  abort() {
    this.active = false;
    try { this.rec?.abort(); } catch {}
    this.rec = null;
  }
}
