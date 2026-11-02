import type { Announcement } from "@/components/AnnouncementCarousel";

export type DialogueItem = {
  id: string; title: string; description: string; topic: string | null; difficulty: string; segments: number;
  estimated_duration: number | null; maximum_score: number; is_free: boolean; locked: boolean; language: string; language_name: string;
  status: "not_started" | "in_progress" | "completed"; best_score: number | null; in_progress_id: string | null; attempts: number;
  last_attempt_id: string | null;
};

export type MockItem = {
  id: string; title: string; is_free: boolean; locked: boolean; attempts: number; best_score: number | null; language_name: string;
  in_progress_id: string | null; dialogues: { title: string; topic: string | null; difficulty: string }[];
  status: "not_started" | "in_progress" | "completed"; last_attempt_id: string | null;
};

export type AttemptSummary = {
  id: string; kind: "mock" | "practice"; title: string; dialogues: string[]; status: string; scoring_status: string;
  total_score: number | null; maximum_score: number; result: "Pass" | "Fail" | null; answered: number; segments: number;
  started_at: string | null; score_validated?: boolean; outcome?: "passed" | "other" | null;
};

export type TopicAverage = { topic: string; average: number | null; count: number };

export type Performance = {
  total_average: number | null; mocks_counted: number; easy_average: number | null; difficult_average: number | null;
  categories: TopicAverage[]; focus: TopicAverage[]; markers: { conditional: number; pass: number; safe: number };
  message: { title: string; text: string };
};

export type CourseRow = {
  id: string; title: string; description: string; lessons: number; completed: number; free_lessons: number; locked: boolean;
  image_url: string | null; next_lesson: { id: string; locked: boolean } | null; teacher?: string | null;
  duration_minutes?: number | null;
};

/** "45 min", "3 hours", "1 hr 30 min". */
export function formatDuration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} min`;
  if (!rest) return `${hours} hour${hours === 1 ? "" : "s"}`;
  return `${hours} hr ${rest} min`;
}

/** YouTube's watch, short and Shorts links refuse to load in a frame: turn them into its embed link. */
export function videoEmbedUrl(url: string) {
  const match = /^https?:\/\/(?:www\.|m\.)?(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:[^#]*&)?v=|shorts\/|live\/))([\w-]{6,})/i.exec(url.trim());
  return match ? `https://www.youtube.com/embed/${match[1]}` : url;
}

export type Dashboard = {
  user: { first_name: string; has_active_plan: boolean; target_exam_date: string | null; days_to_exam: number | null };
  average_mock_score: number | null; average_dialogue_score: number | null; mock_max: number; dialogue_max: number;
  dialogues_available: number; dialogues_total: number; mock_tests_available: number;
  average_over: number | null; scores_shown: boolean; scores_validated: boolean; mock_scores_counted: number; dialogue_scores_counted: number;
  performance: Performance; recommended_course: CourseRow | null;
  unfinished: AttemptSummary[]; recent: AttemptSummary[]; quick_start: DialogueItem | null;
  announcements: Announcement[];
};

/** Label above a course card. */
export function courseState(c: CourseRow) {
  if (!c.completed) return "Available course";
  return c.completed >= c.lessons ? "Completed" : "In progress";
}

/** Start / Resume goes straight to the course content (the next lesson, with the course's lessons beside it). */
export function courseAction(c: Pick<CourseRow, "id" | "lessons" | "completed" | "next_lesson">): { label: string; href: string } | null {
  if (!c.next_lesson) return null;
  if (c.next_lesson.locked) return { label: "Unlock", href: "/pricing" };
  const label = !c.completed ? "Start Course" : c.completed >= c.lessons ? "Review Course" : "Resume Course";
  return { label, href: `/courses/${c.id}/lessons/${c.next_lesson.id}` };
}

export function minutes(seconds: number | null) {
  return seconds ? `${Math.max(1, Math.round(seconds / 60))} min` : "";
}
