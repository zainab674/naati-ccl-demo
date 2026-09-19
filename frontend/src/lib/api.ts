export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    cache: "no-store",
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json", ...headers } : headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {}
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth")) {
      window.location.assign(`${window.location.origin}/login`);
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

// ---------- types

export type User = {
  id: string; email: string; name: string; role: "student" | "assessor"; exam_date: string | null; flagged: boolean;
  test_language: string | null;
};

export type Language = { code: string; name: string; native: string; stt_locale: string; available: boolean };

export type Activity = {
  id: string; number: number; title: string; scenario: string; domain: string; difficulty: string;
  language_pair: string; segment_count: number; duration_seconds: number; status: string; practiced?: boolean;
  speakers: Record<string, { role: string; gender: string }>;
};

export type AttemptSummary = {
  id: string; mode: "practice" | "mock"; status: string; titles: string[]; started_at: string;
  total: number | null; total_max: number | null; passed: boolean | null;
};

export type Issue = {
  category: string; check: string; severity: "minor" | "major" | "critical"; quote: string; explanation: string;
  possibly_transcription_error?: boolean;
};

export type MarkingT = {
  id: string; source: "ai" | "assessor"; marker: string; issues: Issue[]; points_deducted: number;
  summary: string; note: string; created_at: string; raw?: Record<string, unknown>;
};

export type SegmentResult = {
  index: number; number: number; speaker: string; source_text: string; reference_text: string; plays: number;
  response: null | {
    id: string; transcript: string; stt_provider: string; stt_confidence: number | null; needs_review: boolean;
    status: string; error: string; has_audio: boolean;
    delivery: { fillers?: string[]; long_pauses?: { after: string; seconds: number }[]; response_latency?: number | null };
    marking: MarkingT | null; ai_marking: MarkingT | null;
  };
};

export type DialogueResult = {
  activity_id: string; title: string; domain: string; difficulty: string; score: number; max: number;
  meets_minimum: boolean; repeats_used: number; repeat_deduction: number; scale: number;
  by_category: { id: string; name: string; points: number }[]; segments: SegmentResult[];
};

export type Results = {
  attempt_id: string; mode: "practice" | "mock"; status: string; pending_segments: number; total: number;
  total_max: number; passed: boolean; pass_rules: { pass_total: number; pass_min_per_dialogue: number };
  reviewed_by_assessor: boolean; started_at: string; submitted_at: string | null; dialogues: DialogueResult[];
};

// ---------- formatting

export const LANG = { en: "English", hi: "Hindi" } as const;

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString("en-AU", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function isHindi(text: string) {
  return /[ऀ-ॿ]/.test(text);
}
