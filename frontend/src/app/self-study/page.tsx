import PlanLanding, { planMetadata } from "@/components/PlanLanding";

export const generateMetadata = () => planMetadata("self-study");

export default function SelfStudyPage() {
  return <PlanLanding planKey="self-study" />;
}
