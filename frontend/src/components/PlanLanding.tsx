import { Check } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { EnrolButton, FaqList, PublicPage, Reviews, Section } from "@/components/public";
import { type Faq, getContent, getPlans, type HomeContent, type PlanContent, type Review } from "@/lib/content";

export async function planMetadata(key: string): Promise<Metadata> {
  const c = await getContent<PlanContent>(key);
  return { title: c?.seo_title ?? c?.title, description: c?.seo_description,
    openGraph: { title: c?.seo_title, description: c?.seo_description } };
}

/** Product landing page: description, what's included, price, reviews, call to action. */
export default async function PlanLanding({ planKey }: { planKey: string }) {
  const [c, plans, reviews, faq, home] = await Promise.all([
    getContent<PlanContent>(planKey), getPlans(), getContent<Review[]>("reviews"), getContent<Faq>("faq"),
    getContent<HomeContent>("home"),
  ]);
  if (!c) notFound();
  const plan = plans.find((p) => p.key === planKey);
  const contact = !plan || plan.contact_only;

  return (
    <PublicPage disclaimer={home?.disclaimer}>
      <section className="bg-gradient-to-b from-brand-50 to-white px-4 py-16 sm:px-6 sm:py-20">
        <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.4fr_1fr] lg:items-start">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">NAATI CCL · English and Filipino</p>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">{c.title}</h1>
            <p className="mt-4 text-lg text-slate-600">{c.tagline}</p>
            <p className="mt-6 text-slate-700">{c.description}</p>
          </div>
          <div className="rounded-2xl bg-white p-7 shadow-sm ring-1 ring-slate-200">
            <div className="text-sm font-medium text-slate-500">Price</div>
            <div className="mt-1 text-3xl font-semibold">
              {plan?.price_display || <span className="text-lg text-slate-500">{contact ? "Contact us for pricing" : "Shown at checkout"}</span>}
            </div>
            <h2 className="mt-6 text-sm font-semibold">What&apos;s included</h2>
            <ul className="mt-3 space-y-3 text-sm">
              {c.included.map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-brand-600" />{f}</li>)}
            </ul>
            <div className="mt-7"><EnrolButton planKey={planKey} contact={contact} contactEmail={c.contact_email} label={c.cta} /></div>
          </div>
        </div>
      </section>
      {reviews?.length ? <Section title="What students say" muted><Reviews reviews={reviews} /></Section> : null}
      {faq?.length ? <Section title="Questions"><FaqList faq={faq} /></Section> : null}
    </PublicPage>
  );
}
