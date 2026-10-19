import PlanLanding, { planMetadata } from "@/components/PlanLanding";

export const generateMetadata = () => planMetadata("coaching");

export default function CoachingPage() {
  return <PlanLanding planKey="coaching" />;
}
