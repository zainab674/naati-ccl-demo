import { CalendarDays } from "lucide-react";

import ComingSoon from "@/components/ComingSoon";

export default function Page() {
  return <ComingSoon icon={CalendarDays} title="Live coaching"
    text="Book one-to-one or small-group online sessions with Benchmark tutors, straight from the calendar."
    points={["Tutor availability calendar with time-zone handling", "Book, reschedule and cancel with reminders",
      "Tutor sees the student's recent attempts and weak categories before the session", "Video link generated per booking"]} />;
}
