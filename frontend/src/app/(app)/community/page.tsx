import { MessagesSquare } from "lucide-react";

import ComingSoon from "@/components/ComingSoon";

export default function Page() {
  return <ComingSoon icon={MessagesSquare} title="Community"
    text="A place for candidates to share results, ask questions and practise with each other."
    points={["Results and feedback discussion", "Link-out to Telegram / WhatsApp groups", "Tutor announcements"]} />;
}
