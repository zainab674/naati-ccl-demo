import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { cx } from "@/components/cx";
import { FeedbackPreview } from "@/components/landing/FeedbackPreview";
import { btnPrimary, btnSecondary, FaqList, PlanCard, PublicPage, Reviews } from "@/components/public";
import { type Faq, type Feature, getContent, getPlans, type HomeContent, type PlanContent, type Review } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const home = await getContent<HomeContent>("home");
  return {
    title: { absolute: home?.seo_title ? `${home.seo_title} | Benchmark Education` : "Benchmark Education | NAATI CCL Practice" },
    description: home?.seo_description,
    openGraph: { title: home?.seo_title, description: home?.seo_description, type: "website" },
  };
}

const h2 = "font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl";
const pressable = "active:translate-y-px transition-[transform,background-color,color]";

export default async function HomePage() {
  const [home, faq, reviews, plans, selfStudy, coaching] = await Promise.all([
    getContent<HomeContent>("home"), getContent<Faq>("faq"), getContent<Review[]>("reviews"), getPlans(),
    getContent<PlanContent>("self-study"), getContent<PlanContent>("coaching"),
  ]);
  const plan = (k: string) => plans.find((p) => p.key === k);
  const cta = home?.hero_cta || "Start free";

  return (
    <PublicPage disclaimer={home?.disclaimer}>
      {/* Hero: the promise on the left, what the feedback actually looks like on the right. */}
      <section className="overflow-hidden px-4 pb-20 pt-12 sm:px-6 lg:pb-28 lg:pt-20">
        <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-12 lg:gap-10">
          <div className="lg:col-span-7">
            <p className="rise inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700 ring-1 ring-brand-100">
              English <span aria-hidden className="text-brand-400">⇄</span> Filipino
            </p>
            <h1 className="rise mt-5 max-w-[22ch] text-balance font-display text-4xl font-semibold leading-[1.06] tracking-tight text-ink sm:text-5xl xl:text-[3.5rem]" style={{ "--d": "60ms" } as React.CSSProperties}>
              {home?.hero_title || "Prepare for the NAATI CCL test"}
            </h1>
            {home?.hero_subtitle && (
              <p className="rise mt-6 max-w-[52ch] text-lg leading-relaxed text-slate-600" style={{ "--d": "120ms" } as React.CSSProperties}>{home.hero_subtitle}</p>
            )}
            <div className="rise mt-9 flex flex-wrap gap-3" style={{ "--d": "180ms" } as React.CSSProperties}>
              <Link href="/signup" className={cx(btnPrimary, pressable, "h-12 px-6 text-[15px]")}>{cta} <ArrowRight className="size-4" /></Link>
              <Link href="#plans" className={cx(btnSecondary, pressable, "h-12 px-6 text-[15px]")}>See plans</Link>
            </div>
          </div>
          <div className="lg:col-span-5">
            <FeedbackPreview />
          </div>
        </div>
      </section>

      {home?.features?.length ? <Features features={home.features} /> : null}

      {home?.how_it_works?.length ? (
        <section className="bg-slate-50 px-4 py-20 sm:px-6 sm:py-24">
          <div className="mx-auto max-w-6xl">
            <h2 className={cx(h2, "reveal")}>How it works</h2>
            <ol className="relative mt-14 grid gap-12 md:grid-cols-3 md:gap-8">
              <div aria-hidden className="absolute left-0 right-0 top-7 hidden h-px bg-gradient-to-r from-brand-200 via-brand-300 to-transparent md:block" />
              {home.how_it_works.map((s, i) => (
                <li key={s.title} className="reveal relative">
                  <div className="relative flex size-14 items-center justify-center rounded-2xl bg-white font-display text-xl font-semibold text-brand-600 shadow-sm ring-1 ring-brand-100">{i + 1}</div>
                  <h3 className="mt-6 font-display text-xl font-semibold text-ink">{s.title}</h3>
                  <p className="mt-2 max-w-[34ch] leading-relaxed text-slate-600">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>
      ) : null}

      <section id="plans" className="scroll-mt-20 px-4 py-20 sm:px-6 sm:py-24">
        <div className="mx-auto max-w-6xl">
          <div className="reveal max-w-2xl">
            <h2 className={h2}>Plans</h2>
            <p className="mt-3 text-lg leading-relaxed text-slate-600">Start free, then choose the plan that suits how you like to prepare.</p>
          </div>
          <div className="reveal mt-12 grid gap-6 md:grid-cols-2">
            <PlanCard plan={plan("self-study")} content={selfStudy} highlight />
            <PlanCard plan={plan("coaching")} content={coaching} />
          </div>
        </div>
      </section>

      {reviews?.length ? (
        <section className="bg-slate-50 px-4 py-20 sm:px-6 sm:py-24">
          <div className="mx-auto max-w-6xl">
            <h2 className={cx(h2, "reveal")}>What students say</h2>
            <div className="reveal mt-12"><Reviews reviews={reviews} /></div>
          </div>
        </section>
      ) : null}

      {faq?.length ? (
        <section id="faq" className={cx("scroll-mt-20 px-4 py-20 sm:px-6 sm:py-24", !reviews?.length && "bg-slate-50")}>
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <h2 className={cx(h2, "reveal lg:sticky lg:top-28")}>Frequently asked questions</h2>
            </div>
            <div className="reveal lg:col-span-8"><FaqList faq={faq} /></div>
          </div>
        </section>
      ) : null}

      <section className="px-4 pb-20 pt-4 sm:px-6 sm:pb-24">
        <div className="reveal relative mx-auto max-w-6xl overflow-hidden rounded-3xl bg-brand-950 px-6 py-14 text-white sm:px-12 sm:py-16">
          <div aria-hidden className="absolute -right-24 -top-24 size-96 rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--color-brand-400)_35%,transparent),transparent)]" />
          <div className="relative flex flex-col items-start justify-between gap-8 md:flex-row md:items-end">
            <div>
              <h2 className="max-w-[18ch] text-balance font-display text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">Try a free practice dialogue today</h2>
              <p className="mt-3 text-lg text-brand-100/80">No payment needed to start.</p>
            </div>
            <Link href="/signup" className={cx(pressable, "inline-flex h-12 shrink-0 items-center gap-2 rounded-lg bg-white px-6 text-[15px] font-semibold text-brand-950 hover:bg-brand-50")}>
              {cta} <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </section>
    </PublicPage>
  );
}

/**
 * Features as an asymmetric bento. Four items (the seeded count) get a 4/2 then 2/4 rhythm with varied surfaces;
 * any other count falls back to an even two-column grid so admin edits never leave an empty cell.
 */
function Features({ features }: { features: Feature[] }) {
  const bento = features.length === 4;
  const spans = ["md:col-span-4", "md:col-span-2", "md:col-span-2", "md:col-span-4"];
  const surfaces = [
    "bg-brand-950 text-white ring-brand-950",
    "bg-brand-50 ring-brand-100",
    "bg-gradient-to-br from-white to-brand-50 ring-slate-200",
    "bg-white ring-slate-200",
  ];
  return (
    <section className="px-4 py-20 sm:px-6 sm:py-24">
      <div className="mx-auto max-w-6xl">
        <h2 className={cx(h2, "reveal")}>What you get</h2>
        <div className={cx("mt-12 grid gap-5", bento ? "md:grid-cols-6" : "md:grid-cols-2")}>
          {features.map((f, i) => {
            const dark = bento && i === 0;
            return (
              <div key={f.title} className={cx(
                "reveal relative flex min-h-56 flex-col justify-end overflow-hidden rounded-2xl p-7 ring-1 sm:p-8",
                bento ? cx(spans[i], surfaces[i]) : "bg-white ring-slate-200",
              )}>
                {dark && <div aria-hidden className="absolute -left-16 -top-20 size-72 rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--color-brand-400)_40%,transparent),transparent)]" />}
                <h3 className={cx("relative font-display font-semibold tracking-tight", dark ? "text-2xl sm:text-3xl" : "text-xl text-ink")}>{f.title}</h3>
                <p className={cx("relative mt-3 max-w-[48ch] leading-relaxed", dark ? "text-brand-100/80" : "text-slate-600")}>{f.body}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
