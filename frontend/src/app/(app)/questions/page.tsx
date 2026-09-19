import { GraduationCap } from "lucide-react";

import ComingSoon from "@/components/ComingSoon";

export default function Page() {
  return <ComingSoon icon={GraduationCap} title="Vocabulary drills"
    text="Quick-fire practice questions on terms and phrases that come up in CCL dialogues."
    points={["Term sets by domain in Hindi and English", "Timed recall drills, spoken or typed",
      "Spaced repetition based on the student's own mistakes", "Built from the same content studio as the dialogues"]} />;
}
