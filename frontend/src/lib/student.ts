export type DialogueItem = {
  id: string; title: string; description: string; topic: string | null; difficulty: string; segments: number;
  estimated_duration: number | null; maximum_score: number; is_free: boolean; locked: boolean; language: string; language_name: string;
  status: "not_started" | "in_progress" | "completed"; best_score: number | null; in_progress_id: string | null; attempts: number;
};

export type MockItem = {
  id: string; title: string; is_free: boolean; locked: boolean; attempts: number; best_score: number | null; language_name: string;
  in_progress_id: string | null; dialogues: { title: string; topic: string | null; difficulty: string }[];
};

export type AttemptSummary = {
  id: string; kind: "mock" | "practice"; title: string; dialogues: string[]; status: string; scoring_status: string;
  total_score: number | null; maximum_score: number; result: "Pass" | "Fail" | null; answered: number; segments: number;
  started_at: string | null;
};

export type Dashboard = {
  user: { first_name: string; has_active_plan: boolean; target_exam_date: string | null; days_to_exam: number | null };
  average_mock_score: number | null; average_dialogue_score: number | null; mock_max: number; dialogue_max: number;
  dialogues_available: number; dialogues_total: number; mock_tests_available: number;
  unfinished: AttemptSummary[]; recent: AttemptSummary[]; quick_start: DialogueItem | null;
};

export function minutes(seconds: number | null) {
  return seconds ? `${Math.max(1, Math.round(seconds / 60))} min` : "";
}
