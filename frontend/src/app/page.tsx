import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { btnPrimary, btnSecondary, FaqList, PlanCard, PublicPage, Reviews, Section } from "@/components/public";
import { type Faq, getContent, getPlans, type HomeContent, type PlanContent, type Review } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const home = await getContent<HomeContent>("home");
  return {
    title: { absolute: home?.seo_title ? `${home.seo_title} | Benchmark Education` : "Benchmark Education | NAATI CCL Practice" },
    description: home?.seo_description,
    openGraph: { title: home?.seo_title, description: home?.seo_description, type: "website" },
  };
}

export default async function HomePage() {
  const [home, faq, reviews, plans, selfStudy, coaching] = await Promise.all([
    getContent<HomeContent>("home"), getContent<Faq>("faq"), getContent<Review[]>("reviews"), getPlans(),
    getContent<PlanContent>("self-study"), getContent<PlanContent>("coaching"),
  ]);
  const plan = (k: string) => plans.find((p) => p.key === k);

  return (
    <PublicPage disclaimer={home?.disclaimer}>
      <section className="bg-gradient-to-b from-brand-50 to-white px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">English and your language</p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-tight text-ink sm:text-5xl">{home?.hero_title}</h1>
            <p className="mt-5 text-lg text-slate-600">{home?.hero_subtitle}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className={btnPrimary}>{home?.hero_cta || "Start free"} <ArrowRight className="size-4" /></Link>
              <Link href="/pricing" className={btnSecondary}>See plans</Link>
            </div>
          </div>
        </div>
      </section>

      {home?.features?.length ? (
        <Section title="What you get">
          <div className="grid gap-6 sm:grid-cols-2">
            {home.features.map((f) => (
              <div key={f.title} className="rounded-xl p-6 ring-1 ring-slate-200">
                <h3 className="font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{f.body}</p>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {home?.how_it_works?.length ? (
        <Section title="How it works" muted>
          <ol className="grid gap-6 md:grid-cols-3">
            {home.how_it_works.map((s, i) => (
              <li key={s.title} className="rounded-xl bg-white p-6 ring-1 ring-slate-200">
                <div className="flex size-8 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">{i + 1}</div>
                <h3 className="mt-4 font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{s.body}</p>
              </li>
            ))}
          </ol>
        </Section>
      ) : null}

      <Section id="plans" title="Plans" subtitle="Start free, then choose the plan that suits how you like to prepare.">
        <div className="grid gap-6 md:grid-cols-2">
          <PlanCard plan={plan("self-study")} content={selfStudy} highlight />
          <PlanCard plan={plan("coaching")} content={coaching} />
        </div>
      </Section>

      {reviews?.length ? <Section title="What students say" muted><Reviews reviews={reviews} /></Section> : null}

      {faq?.length ? <Section id="faq" title="Frequently asked questions"><FaqList faq={faq} /></Section> : null}

      <Section muted>
        <div className="flex flex-col items-start justify-between gap-6 rounded-2xl bg-brand-950 p-8 text-white sm:flex-row sm:items-center sm:p-10">
          <div>
            <h2 className="text-2xl font-semibold">Try a free practice dialogue today</h2>
            <p className="mt-2 text-brand-100/80">No payment needed to start.</p>
          </div>
          <Link href="/signup" className="inline-flex h-11 items-center rounded-lg bg-white px-5 text-sm font-semibold text-brand-950 hover:bg-brand-50">Create a free account</Link>
        </div>
      </Section>
    </PublicPage>
  );
}
