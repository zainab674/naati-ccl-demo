export type Deductions = { accuracy: number; language: number; fluency: number; total: number };

type ItemBase = { id: string; deduction: number; explanation: string; confidence: number | null; overridden: boolean };
export type AccuracyItem = ItemBase & { result: string; meaning_unit?: number; source_meaning: string; student_meaning: string; suggested_version: string };
export type LanguageItem = ItemBase & { type: string; student_text: string; suggested_version: string; needs_review: boolean; detection_method: string };
export type FluencyItem = ItemBase & { type: string; transcript_excerpt: string; timestamp_seconds: number | null; duration_seconds: number | null; detection_method: string };

export type SegmentResult = {
  segment_attempt_id: string; number: number; direction: string; source_language: string; target_language: string;
  source_transcript: string | null; answered: boolean; skipped: boolean; has_recording: boolean; transcript: string;
  stt_provider: string; feedback: string; scoring_status: string; needs_review: boolean; reviewed: boolean; play_count: number;
  deductions: Deductions; accuracy: AccuracyItem[]; insertions: AccuracyItem[]; language: LanguageItem[]; fluency: FluencyItem[];
  // admin only
  scoring_error?: string; scoring_confidence?: number | null; timing?: Record<string, unknown>;
  stt_words?: { word: string; start: number; end: number }[];
  reviews?: { id: string; target_type: string; target_id: string | null; original_deduction: number; revised_deduction: number; notes: string; created_at: string }[];
};

export type DialogueResult = {
  dialogue_attempt_id: string; title: string; position: number; topic: string | null; difficulty: string;
  score: number | null; maximum_score: number; passing_score: number; result: "Pass" | "Fail" | null; scoring_status: string;
  total_repeats: number; attempt_number: number; dialogue_version: number; deductions: Deductions; segments: SegmentResult[];
};

export type Results = {
  id: string; kind: "mock" | "practice"; title: string; status: string; scoring_status: string; pending_segments: number;
  total_score: number | null; maximum_score: number; result: "Pass" | "Fail" | null; reasons: string[]; submitted_at: string | null;
  pass_rules: { pass_total: number; pass_min_per_dialogue: number; dialogue_max: number; total_max: number };
  demo_scoring: boolean; deductions: Deductions; dialogues: DialogueResult[];
  history: { id: string; total_score: number | null; maximum_score: number; result: string | null; submitted_at: string | null }[];
};

export const LABELS: Record<string, string> = {
  Omission: "Omission", Distortion: "Distortion", Insertion: "Insertion", Correct: "Correct",
  Grammar: "Grammar", UnidiomaticUsage: "Unidiomatic usage", Register: "Register", SentenceStructure: "Sentence structure",
  Pronunciation: "Pronunciation", Pause: "Long pause", StartDelay: "Late start", Hesitation: "Hesitation", SelfCorrection: "Self-correction",
};
