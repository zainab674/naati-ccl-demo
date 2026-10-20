import { existsSync } from "node:fs";
import path from "node:path";

import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { cx } from "@/components/cx";
import { FeedbackPreview } from "@/components/landing/FeedbackPreview";
import { CinematicHero, type HeroStat } from "@/components/landing/Hero";
import { Aurora, FaqAccordion, Magnetic, MotionRoot, Reveal, ScrollLine, SpotlightCard, Stagger, StaggerItem, Tilt } from "@/components/landing/motion";
import { PlanCard, PublicPage, Reviews } from "@/components/public";
import { type Faq, type Feature, getContent, getLanguages, getPlans, getTheme, type HomeContent, type PlanContent, type Review } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const [home, theme] = await Promise.all([getContent<HomeContent>("home"), getTheme()]);
  const name = theme?.name || "Benchmark Education";
  return {
    title: { absolute: home?.seo_title ? `${home.seo_title} | ${name}` : `${name} | NAATI CCL Practice` },
    description: home?.seo_description,
    openGraph: { title: home?.seo_title, description: home?.seo_description, type: "website" },
  };
}

const h2 = "font-serif text-4xl font-medium leading-[1.08] tracking-tight text-white sm:text-5xl";
const lead = "text-lg leading-relaxed text-brand-100/70";

// Drop a photo here (around 2400x1400, dark-friendly) to replace the drawn horizon scene in the hero.
const HERO_IMAGE = "/landing/hero.jpg";

export default async function HomePage() {
  const [home, faq, reviews, plans, selfStudy, coaching, languages] = await Promise.all([
    getContent<HomeContent>("home"), getContent<Faq>("faq"), getContent<Review[]>("reviews"), getPlans(),
    getContent<PlanContent>("self-study"), getContent<PlanContent>("coaching"), getLanguages(),
  ]);
  const plan = (k: string) => plans.find((p) => p.key === k);
  const cta = home?.hero_cta || "Start free";
  const heroImage = existsSync(path.join(process.cwd(), "public", HERO_IMAGE)) ? HERO_IMAGE : null;

  // Facts only: the CCL test format (2 dialogues, 90 marks), the live language count, and the free start.
  const stats: HeroStat[] = [
    ...(languages.length ? [{ value: String(languages.length), label: "Languages paired with English" }] : []),
    { value: "2", label: "Dialogues in every mock test" },
    { value: "90", label: "Marks, scored like the real test" },
    { value: "Free", label: "Practice dialogue to start" },
  ];

  return (
    <MotionRoot>
    <PublicPage disclaimer={home?.disclaimer} dark>
      <CinematicHero
        title={home?.hero_title || "Prepare for the NAATI CCL test"}
        subtitle={home?.hero_subtitle}
        cta={cta}
        languages={languages}
        image={heroImage}
        stats={stats}
      />

      {/* The product, up close: one segment marked the way the platform marks it. */}
      <section className="relative isolate overflow-hidden px-4 py-24 sm:px-6 sm:py-32">
        <div aria-hidden className="absolute left-1/2 top-0 -z-10 h-px w-[80%] -translate-x-1/2 bg-gradient-to-r from-transparent via-brand-300/40 to-transparent" />
        <div className="mx-auto grid max-w-6xl items-center gap-16 lg:grid-cols-12">
          <Reveal className="lg:col-span-5">
            <h2 className={h2}>See exactly where you <em className="text-brand-200">lost marks</em></h2>
            <p className={cx(lead, "mt-6 max-w-[44ch]")}>Every Meaning Unit is checked for omissions, insertions and distortions, and your timing is measured from the recording.</p>
          </Reveal>
          <Reveal className="lg:col-span-7" delay={0.15}>
            <Tilt className="mx-auto max-w-xl"><FeedbackPreview /></Tilt>
          </Reveal>
        </div>
      </section>

      {home?.features?.length ? <Features features={home.features} /> : null}

      {home?.how_it_works?.length ? (
        <section className="relative px-4 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <Reveal><h2 className={h2}>How it works</h2></Reveal>
            <div className="relative mt-16">
              <ScrollLine className="absolute left-0 right-0 top-8 hidden md:block" />
              <Stagger className="grid gap-12 md:grid-cols-3 md:gap-8" gap={0.15}>
                {home.how_it_works.map((s, i) => (
                  <StaggerItem key={s.title} className="relative">
                    <div className="relative flex size-16 items-center justify-center rounded-full bg-brand-950 font-serif text-2xl italic text-brand-200 shadow-[0_0_40px_-8px_var(--color-brand-400)] ring-1 ring-brand-300/40">{i + 1}</div>
                    <h3 className="mt-7 font-display text-xl font-semibold text-white">{s.title}</h3>
                    <p className="mt-2 max-w-[34ch] leading-relaxed text-brand-100/65">{s.body}</p>
                  </StaggerItem>
                ))}
              </Stagger>
            </div>
          </div>
        </section>
      ) : null}

      <section id="plans" className="relative isolate scroll-mt-20 overflow-hidden px-4 py-24 sm:px-6 sm:py-32">
        <div aria-hidden className="absolute left-1/2 top-1/3 -z-10 size-[50rem] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--color-brand-500)_22%,transparent),transparent)]" />
        <div className="mx-auto max-w-6xl">
          <Reveal className="mx-auto max-w-2xl text-center">
            <h2 className={h2}>Plans</h2>
            <p className={cx(lead, "mt-4")}>Start free, then choose the plan that suits how you like to prepare.</p>
          </Reveal>
          <Stagger className="mx-auto mt-14 grid max-w-5xl gap-6 md:grid-cols-2" gap={0.12}>
            <SpotlightCard className="flex rounded-[1.1rem] bg-gradient-to-b from-brand-300/70 via-brand-400/20 to-white/5 p-px shadow-[0_30px_80px_-30px_var(--color-brand-400)] [&>div:last-child]:flex-1">
              <PlanCard plan={plan("self-study")} content={selfStudy} highlight />
            </SpotlightCard>
            <SpotlightCard className="flex rounded-[1.1rem] bg-white/10 p-px [&>div:last-child]:flex-1">
              <PlanCard plan={plan("coaching")} content={coaching} />
            </SpotlightCard>
          </Stagger>
        </div>
      </section>

      {reviews?.length ? (
        <section className="px-4 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <Reveal><h2 className={h2}>What students say</h2></Reveal>
            <Reveal className="mt-12" delay={0.1}><Reviews reviews={reviews} /></Reveal>
          </div>
        </section>
      ) : null}

      {faq?.length ? (
        <section id="faq" className="scroll-mt-20 px-4 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <Reveal className="lg:sticky lg:top-28"><h2 className={h2}>Questions, <em className="text-brand-200">answered</em></h2></Reveal>
            </div>
            <div className="lg:col-span-8"><FaqAccordion faq={faq} /></div>
          </div>
        </section>
      ) : null}

      <section className="px-4 pb-24 pt-8 sm:px-6 sm:pb-32">
        <Reveal>
          <div className="relative isolate mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-gradient-to-br from-brand-700 via-brand-800 to-brand-950 px-6 py-16 text-center ring-1 ring-white/15 sm:px-12 sm:py-24">
            <Aurora />
            <h2 className="mx-auto max-w-[20ch] text-balance font-serif text-4xl font-medium leading-[1.08] tracking-tight text-white sm:text-6xl">Try a free practice dialogue today</h2>
            <p className="mt-5 text-lg text-brand-50/80">No payment needed to start.</p>
            <div className="mt-10 flex justify-center">
              <Magnetic>
                <Link href="/signup" className="group inline-flex h-12 items-center gap-2 rounded-full bg-white px-8 text-[15px] font-semibold text-brand-950 shadow-[0_10px_40px_-10px_rgb(0_0_0/0.5)] transition-colors hover:bg-brand-50">
                  {cta} <ArrowRight className="size-4 transition-transform duration-300 group-hover:translate-x-1" />
                </Link>
              </Magnetic>
            </div>
          </div>
        </Reveal>
      </section>
    </PublicPage>
    </MotionRoot>
  );
}

/**
 * Features as an asymmetric bento of glass tiles with a cursor spotlight. Four items (the seeded count) get a
 * 4/2 then 2/4 rhythm with varied light; any other count falls back to an even two-column grid.
 */
function Features({ features }: { features: Feature[] }) {
  const bento = features.length === 4;
  const spans = ["md:col-span-4", "md:col-span-2", "md:col-span-2", "md:col-span-4"];
  const surfaces = [
    "bg-gradient-to-br from-brand-500/40 via-brand-700/30 to-brand-900/40 ring-brand-300/30",
    "bg-white/[0.04] ring-white/10",
    "bg-gradient-to-br from-white/[0.06] to-brand-400/10 ring-white/10",
    "bg-gradient-to-br from-amber-300/[0.12] via-white/[0.03] to-transparent ring-amber-200/20",
  ];
  const tints = ["var(--color-brand-200)", "var(--color-brand-300)", "var(--color-brand-300)", "#fcd34d"];
  return (
    <section className="px-4 py-24 sm:px-6 sm:py-32">
      <div className="mx-auto max-w-6xl">
        <Reveal><h2 className={h2}>What you get</h2></Reveal>
        <Stagger className={cx("mt-14 grid gap-5", bento ? "md:grid-cols-6" : "md:grid-cols-2")} gap={0.1}>
          {features.map((f, i) => {
            const big = bento && i === 0;
            return (
              <SpotlightCard key={f.title} tint={bento ? tints[i] : undefined} className={cx(
                "flex min-h-60 flex-col justify-end rounded-3xl p-8 ring-1 backdrop-blur-sm",
                bento ? cx(spans[i], surfaces[i]) : "bg-white/[0.04] ring-white/10",
              )}>
                <h3 className={cx("relative font-semibold tracking-tight text-white", big ? "font-serif text-3xl font-medium sm:text-4xl" : "font-display text-xl")}>{f.title}</h3>
                <p className="relative mt-3 max-w-[48ch] leading-relaxed text-brand-100/70">{f.body}</p>
              </SpotlightCard>
            );
          })}
        </Stagger>
      </div>
    </section>
  );
}
