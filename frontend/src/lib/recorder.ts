/**
 * Chunk-safe recording upload. MediaRecorder emits a chunk every few seconds; each chunk is PUT as a numbered part
 * while the student is still speaking, with retries. "complete" asks the server to join the parts. A failed part
 * stays in memory so the student can retry without re-recording.
 */
export class ChunkUploader {
  private parts: Blob[] = [];
  private uploaded = new Set<number>();
  private queue: Promise<void> = Promise.resolve();
  private failed: Error | null = null;
  // One id per take: parts are stored under it, so a late retry from a discarded take cannot overwrite this one.
  private readonly take = crypto.randomUUID().replace(/-/g, "");

  constructor(private baseUrl: string) {}

  add(chunk: Blob) {
    if (!chunk.size) return;
    const index = this.parts.length;
    this.parts.push(chunk);
    this.queue = this.queue.then(() => this.send(index)).catch((e) => { this.failed = e; });
  }

  private async send(index: number) {
    if (this.uploaded.has(index)) return;
    // Network errors, 429 and 5xx are retried with backoff; other 4xx are final (e.g. attempt already submitted).
    let lastError = new Error("Upload failed");
    for (let attempt = 0; attempt < 4; attempt++) {
      if (attempt) await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
      let res: Response;
      try {
        res = await fetch(`/api${this.baseUrl}/parts/${index}?recording=${this.take}`, {
          method: "PUT", body: this.parts[index], credentials: "same-origin",
          headers: { "Content-Type": "application/octet-stream" },
        });
      } catch {
        lastError = new Error("Network problem while uploading your recording");
        continue;
      }
      if (res.ok) { this.uploaded.add(index); return; }
      if (res.status < 500 && res.status !== 429) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : `Upload failed (${res.status})`);
      }
      lastError = new Error(`Upload failed (${res.status})`);
    }
    throw lastError;
  }

  /** Wait for every part, retrying any that failed, then join them on the server. */
  async finish(mime: string, durationSeconds: number | null, timing: Record<string, number>) {
    await this.queue;
    this.failed = null;
    for (let i = 0; i < this.parts.length; i++) await this.send(i);
    if (!this.parts.length) throw new Error("Nothing was recorded. Check your microphone.");
    const res = await fetch(`/api${this.baseUrl}/complete`, {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parts: this.parts.length, mime, duration_seconds: durationSeconds, timing, recording: this.take }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : `Saving the recording failed (${res.status})`);
    }
  }

  get partCount() { return this.parts.length; }
}

export function pickMime() {
  const opts = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return opts.find((m) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m)) ?? "";
}

/** A short two-tone sound for the equipment check (no file needed). */
export function playTestSound(): Promise<void> {
  const ctx = new AudioContext();
  const tone = (freq: number, start: number, dur: number) => {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.25, ctx.currentTime + start);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
    o.connect(g).connect(ctx.destination);
    o.start(ctx.currentTime + start);
    o.stop(ctx.currentTime + start + dur);
  };
  tone(660, 0, 0.4);
  tone(880, 0.45, 0.4);
  tone(660, 0.9, 0.6);
  return new Promise((r) => setTimeout(() => { ctx.close(); r(); }, 1600));
}
