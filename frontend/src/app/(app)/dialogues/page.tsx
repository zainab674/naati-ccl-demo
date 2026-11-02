import { redirect } from "next/navigation";

// Dialogues and mock tests share one page since the client's Round 1 revision.
export default function DialoguesPage() {
  redirect("/mock-tests?mode=dialogue");
}
