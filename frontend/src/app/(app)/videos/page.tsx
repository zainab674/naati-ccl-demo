import { PlayCircle } from "lucide-react";

import ComingSoon from "@/components/ComingSoon";

export default function Page() {
  return <ComingSoon icon={PlayCircle} title="Video lessons"
    text="Short tutor-led videos on CCL technique, organised by domain, and tied to the dialogues students struggle with."
    points={["Note-taking and memory technique for long segments", "Domain vocabulary walkthroughs (health, legal, financial…)",
      "Worked examples: common mistakes on real practice segments", "Streamed with the same protection as the test audio"]} />;
}
