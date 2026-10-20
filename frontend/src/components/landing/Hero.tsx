"use client";

import { ArrowRight } from "lucide-react";
import { motion, type MotionValue, useScroll, useTransform } from "motion/react";
import Link from "next/link";
import { type CSSProperties, useRef } from "react";

import { cx } from "../cx";
import { Aurora, Magnetic, useReduced } from "./motion";

export type HeroLanguage = { code: string; name: string; native_name?: string | null };
export type HeroStat = { value: string; label: string };

/**
 * Full-height cinematic hero: a drawn horizon scene,
 * a centred serif headline, and glass panels carrying the real languages on either side.
 * Panels float and parallax at different depths; all of it is static under reduced motion.
 */
export function CinematicHero({ title, subtitle, cta, languages, stats }: {
  title: string; subtitle?: string; cta: string; languages: HeroLanguage[]; stats: HeroStat[];
}) {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReduced();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "18%"]);
  const contentY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const fade = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

  // Filipino is the launch language, so it leads; the panels show up to four languages in their own script.
  const panels = [...languages].sort((a, b) => Number(b.code.startsWith("fil")) - Number(a.code.startsWith("fil"))).slice(0, 4);
  const left = panels.filter((_, i) => i % 2 === 0);
  const right = panels.filter((_, i) => i % 2 === 1);
  const count = languages.length;

  return (
    <section ref={ref} className="relative isolate flex min-h-[calc(100dvh-4rem)] flex-col overflow-hidden">
      {/* Scene */}
      <motion.div aria-hidden className="absolute inset-0 -z-20" style={reduce ? undefined : { y: bgY }}>
        <div className="absolute inset-0 bg-[linear-gradient(180deg,var(--color-brand-950)_0%,color-mix(in_oklab,var(--color-brand-800)_85%,black)_42%,color-mix(in_oklab,var(--color-brand-600)_60%,#f59e0b_12%)_62%,var(--color-brand-950)_63%,var(--color-brand-950)_100%)]" />
      </motion.div>
      <Aurora className="-z-10" />
      {/* Sun on the horizon, its light beam, and the reflective floor. */}
      <div aria-hidden className="absolute left-1/2 top-[62%] -z-10 h-40 w-[70rem] max-w-[140vw] -translate-x-1/2 -translate-y-1/2 rounded-[100%] bg-[radial-gradient(closest-side,color-mix(in_oklab,#fde68a_55%,transparent),color-mix(in_oklab,var(--color-brand-300)_25%,transparent)_45%,transparent)] blur-md" />
      <motion.div aria-hidden className="absolute left-1/2 top-0 -z-10 h-[62%] w-[38rem] max-w-[90vw] -translate-x-1/2 bg-[linear-gradient(to_bottom,transparent,color-mix(in_oklab,var(--color-brand-200)_14%,transparent))] [clip-path:polygon(42%_0,58%_0,100%_100%,0_100%)]"
        animate={reduce ? undefined : { opacity: [0.5, 1, 0.5] }} transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }} />
      <div aria-hidden className="absolute inset-x-0 bottom-0 top-[62%] -z-10 bg-[linear-gradient(to_bottom,color-mix(in_oklab,var(--color-brand-300)_18%,transparent),transparent_40%)]" />
      <div aria-hidden className="absolute inset-x-[8%] top-[62%] -z-10 h-px bg-gradient-to-r from-transparent via-amber-100/70 to-transparent" />

      {/* Glass language panels */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 hidden lg:block">
        {left.map((l, i) => <GlassPanel key={l.code} lang={l} side="left" index={i} progress={scrollYProgress} />)}
        {right.map((l, i) => <GlassPanel key={l.code} lang={l} side="right" index={i} progress={scrollYProgress} />)}
      </div>

      {/* Copy */}
      <motion.div className="relative mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-4 pb-44 pt-12 text-center sm:px-6 md:pb-36"
        style={reduce ? undefined : { y: contentY, opacity: fade }}>
        <p className="hero-in flex items-center gap-4 text-xs font-medium uppercase tracking-[0.32em] text-brand-100/80">
          <span aria-hidden className="h-px w-8 bg-brand-100/40" />English ⇄ {count ? `${count} languages` : "your language"}<span aria-hidden className="h-px w-8 bg-brand-100/40" />
        </p>
        <h1 className="mt-7 max-w-[18ch] text-balance pb-1 font-serif text-5xl font-medium leading-[1.04] tracking-tight text-white drop-shadow-[0_4px_30px_rgb(0_0_0/0.35)] sm:text-6xl lg:text-[4.25rem]">
          {title.split(" ").map((w, i) => (
            <span key={i} className="hero-in inline-block whitespace-pre" style={{ "--d": `${250 + i * 60}ms` } as CSSProperties}>
              {w}{" "}
            </span>
          ))}
        </h1>
        {subtitle && (
          <p className="hero-in mt-7 max-w-[46ch] text-lg leading-relaxed text-brand-50/80" style={{ "--d": "800ms" } as CSSProperties}>{subtitle}</p>
        )}
        <div className="hero-in mt-10 flex flex-wrap items-center justify-center gap-3" style={{ "--d": "1000ms" } as CSSProperties}>
          <Magnetic>
            <Link href="/signup" className="group inline-flex h-12 items-center gap-2 rounded-full bg-white px-7 text-[15px] font-semibold text-brand-950 shadow-[0_10px_40px_-10px_color-mix(in_oklab,var(--color-brand-200)_80%,transparent)] transition-colors hover:bg-brand-50">
              {cta} <ArrowRight className="size-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
          </Magnetic>
          <Link href="#plans" className="inline-flex h-12 items-center rounded-full bg-white/10 px-7 text-[15px] font-semibold text-white ring-1 ring-white/20 backdrop-blur-md transition-colors hover:bg-white/15">
            See plans
          </Link>
        </div>
      </motion.div>

      {/* Facts along the floor */}
      {stats.length > 0 && (
        <dl style={{ "--d": "1300ms" } as CSSProperties}
          className="hero-in absolute inset-x-0 bottom-0 mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-5 px-4 pb-8 sm:px-6 md:grid-cols-4">
          {stats.map((s, i) => (
            <div key={s.label} className={cx("border-l border-white/15 pl-4", i >= 2 && "md:text-left")}>
              <dt className="sr-only">{s.label}</dt>
              <dd className="font-serif text-3xl text-white">{s.value}</dd>
              <dd className="mt-1 text-xs leading-snug text-brand-100/70">{s.label}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

function GlassPanel({ lang, side, index, progress }: { lang: HeroLanguage; side: "left" | "right"; index: number; progress: MotionValue<number> }) {
  const reduce = useReduced();
  const near = index === 0;
  const y = useTransform(progress, [0, 1], [0, near ? -160 : -90]);
  const pos = side === "left"
    ? (near ? "left-[4%] top-[26%] h-[22rem] w-44" : "left-[17%] top-[36%] h-[15rem] w-32")
    : (near ? "right-[4%] top-[24%] h-[23rem] w-44" : "right-[17%] top-[38%] h-[14rem] w-32");
  return (
    <motion.div className={cx("absolute", side === "left" ? "hero-in-l" : "hero-in-r", pos)} style={{ ...(reduce ? {} : { y }), "--d": `${500 + index * 200}ms` } as CSSProperties}>
      <motion.div
        className="flex h-full w-full flex-col justify-between rounded-2xl bg-gradient-to-b from-white/20 via-white/[0.07] to-white/[0.02] p-5 shadow-[inset_0_1px_0_rgb(255_255_255/0.4),0_30px_60px_-20px_rgb(0_0_0/0.5)] ring-1 ring-white/25 backdrop-blur-md"
        style={{ transformPerspective: 900, rotateY: side === "left" ? 22 : -22 }}
        animate={reduce ? undefined : { y: [0, -12, 0] }}
        transition={{ duration: 7 + index * 1.5, repeat: Infinity, ease: "easeInOut" }}
      >
        <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-white/70">{lang.name}</span>
        <span lang={lang.code} className={cx("font-serif leading-none text-white/95", near ? "text-3xl" : "text-2xl")}>{lang.native_name || lang.name}</span>
      </motion.div>
      {/* Reflection on the floor */}
      <div className="mt-2 h-16 w-full rounded-2xl bg-gradient-to-b from-white/10 to-transparent opacity-60 blur-sm" style={{ transform: `perspective(900px) rotateY(${side === "left" ? 22 : -22}deg) scaleY(-1)` }} />
    </motion.div>
  );
}
