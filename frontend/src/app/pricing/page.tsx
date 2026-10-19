import type { Metadata } from "next";

import { FaqList, PlanCard, PublicPage, Section } from "@/components/public";
import { type Faq, getContent, getPlans, type HomeContent, type PlanContent } from "@/lib/content";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Compare the Self-Study and Coaching plans for NAATI CCL preparation in English and Filipino.",
};

export default async function PricingPage({ searchParams }: PageProps<"/pricing">) {
  const [plans, selfStudy, coaching, faq, home, params] = await Promise.all([
    getPlans(), getContent<PlanContent>("self-study"), getContent<PlanContent>("coaching"), getContent<Faq>("faq"),
    getContent<HomeContent>("home"), searchParams,
  ]);
  return (
    <PublicPage disclaimer={home?.disclaimer}>
      <Section title="Pricing" subtitle="Self-Study or Coaching. Start with a free account and upgrade when you're ready.">
        {params.cancelled && (
          <div className="mb-6 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200">Checkout was cancelled. You have not been charged.</div>
        )}
        <div className="grid gap-6 md:grid-cols-2">
          <PlanCard plan={plans.find((p) => p.key === "self-study")} content={selfStudy} highlight />
          <PlanCard plan={plans.find((p) => p.key === "coaching")} content={coaching} />
        </div>
      </Section>
      {faq?.length ? <Section title="Questions" muted><FaqList faq={faq} /></Section> : null}
    </PublicPage>
  );
}
