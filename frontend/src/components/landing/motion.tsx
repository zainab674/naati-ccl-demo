"use client";

/**
 * Motion leaves for the landing page. Each one degrades to a static render under prefers-reduced-motion,
 * and continuous values (cursor position, scroll progress) live in motion values, never React state.
 */
import { AnimatePresence, motion, MotionConfig, useMotionTemplate, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";
import { Plus } from "lucide-react";
import { type ReactNode, useRef, useState, useSyncExternalStore } from "react";

import type { Faq } from "@/lib/content";
import { cx } from "../cx";

export const EASE = [0.16, 1, 0.3, 1] as const;

const noop = () => () => {};

/**
 * Reduced-motion preference that is false until after hydration, so the server HTML and the first client render
 * always match. Movement is also switched off globally by MotionRoot (MotionConfig reducedMotion="user").
 */
export function useReduced() {
  const pref = useReducedMotion();
  const hydrated = useSyncExternalStore(noop, () => true, () => false);
  return hydrated && !!pref;
}

export function MotionRoot({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/** Fades and lifts its children in once, when scrolled into view (or on load, for the hero). */
export function Reveal({ children, className, delay = 0, y = 24, onLoad }: { children: ReactNode; className?: string; delay?: number; y?: number; onLoad?: boolean }) {
  const to = { opacity: 1, y: 0, filter: "blur(0px)" };
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y, filter: "blur(6px)" }}
      {...(onLoad ? { animate: to } : { whileInView: to, viewport: { once: true, amount: 0.25 } })}
      transition={{ duration: 0.8, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/** Container whose direct StaggerItem children enter one after another. */
export function Stagger({ children, className, gap = 0.08, onLoad }: { children: ReactNode; className?: string; gap?: number; onLoad?: boolean }) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      {...(onLoad ? { animate: "show" } : { whileInView: "show", viewport: { once: true, amount: 0.2 } })}
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap } } }}
    >
      {children}
    </motion.div>
  );
}

export const itemVariants = {
  hidden: { opacity: 0, y: 22, filter: "blur(6px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.75, ease: EASE } },
};

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={itemVariants}>{children}</motion.div>;
}

/** Card with a soft light that follows the cursor, plus a small lift on hover. */
export function SpotlightCard({ children, className, tint = "var(--color-brand-300)" }: { children: ReactNode; className?: string; tint?: string }) {
  const reduce = useReduced();
  const x = useMotionValue(-400);
  const y = useMotionValue(-400);
  const bg = useMotionTemplate`radial-gradient(420px circle at ${x}px ${y}px, color-mix(in oklab, ${tint} 22%, transparent), transparent 70%)`;
  return (
    <motion.div
      variants={itemVariants}
      whileHover={reduce ? undefined : { y: -6 }}
      transition={{ type: "spring", stiffness: 260, damping: 24 }}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        x.set(e.clientX - r.left);
        y.set(e.clientY - r.top);
      }}
      onPointerLeave={() => { x.set(-400); y.set(-400); }}
      className={cx("group relative overflow-hidden", className)}
    >
      {!reduce && <motion.div aria-hidden className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" style={{ background: bg }} />}
      {children}
    </motion.div>
  );
}

/** Pulls its child gently toward the cursor (primary CTAs only). */
export function Magnetic({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReduced();
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const x = useSpring(mx, { stiffness: 220, damping: 18, mass: 0.4 });
  const y = useSpring(my, { stiffness: 220, damping: 18, mass: 0.4 });
  if (reduce) return <span className={className}>{children}</span>;
  return (
    <motion.span
      className={cx("inline-flex", className)}
      style={{ x, y }}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        mx.set((e.clientX - r.left - r.width / 2) * 0.25);
        my.set((e.clientY - r.top - r.height / 2) * 0.35);
      }}
      onPointerLeave={() => { mx.set(0); my.set(0); }}
      whileTap={{ scale: 0.97 }}
    >
      {children}
    </motion.span>
  );
}

/** 3D tilt that tracks the cursor; used to give the hero feedback card physical depth. */
export function Tilt({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReduced();
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const rotateY = useSpring(useTransform(px, [0, 1], [-7, 7]), { stiffness: 150, damping: 18 });
  const rotateX = useSpring(useTransform(py, [0, 1], [6, -6]), { stiffness: 150, damping: 18 });
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <div className={cx("[perspective:1200px]", className)}>
      <motion.div
        style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          px.set((e.clientX - r.left) / r.width);
          py.set((e.clientY - r.top) / r.height);
        }}
        onPointerLeave={() => { px.set(0.5); py.set(0.5); }}
      >
        {children}
      </motion.div>
    </div>
  );
}

/** Line that draws across the how-it-works steps in step with the scroll. */
export function ScrollLine({ className }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReduced();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 85%", "end 45%"] });
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 30 });
  return (
    <div ref={ref} aria-hidden className={cx("h-px bg-white/10", className)}>
      <motion.div className="h-full origin-left bg-gradient-to-r from-brand-300 via-brand-200 to-amber-200 shadow-[0_0_12px_var(--color-brand-300)]" style={{ scaleX: reduce ? 1 : scaleX }} />
    </div>
  );
}

/** Slow-moving coloured light behind a section. Purely decorative, frozen under reduced motion. */
export function Aurora({ className }: { className?: string }) {
  const reduce = useReduced();
  const loop = (d: number) => (reduce ? { duration: 0 } : { duration: d, repeat: Infinity, repeatType: "mirror" as const, ease: "easeInOut" as const });
  return (
    <div aria-hidden className={cx("pointer-events-none absolute inset-0 -z-10 overflow-hidden", className)}>
      <motion.div
        className="absolute -right-[10%] -top-[30%] size-[46rem] rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--color-brand-400)_55%,transparent),transparent)] blur-2xl"
        animate={reduce ? undefined : { x: [0, -80, 30], y: [0, 60, -20], scale: [1, 1.15, 0.95] }}
        transition={loop(22)}
      />
      <motion.div
        className="absolute -bottom-[35%] -left-[15%] size-[40rem] rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,#f59e0b_28%,transparent),transparent)] blur-2xl"
        animate={reduce ? undefined : { x: [0, 90, -20], y: [0, -50, 10], scale: [1, 0.9, 1.1] }}
        transition={loop(28)}
      />
      <motion.div
        className="absolute left-[35%] top-[20%] size-[28rem] rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--color-brand-600)_50%,transparent),transparent)] blur-3xl"
        animate={reduce ? undefined : { x: [0, 60, -60], y: [0, 40, -30] }}
        transition={loop(34)}
      />
    </div>
  );
}

/** FAQ accordion with animated open/close; one item open at a time. */
export function FaqAccordion({ faq }: { faq: Faq }) {
  const [open, setOpen] = useState<number | null>(0);
  const reduce = useReduced();
  return (
    <Stagger className="space-y-3" gap={0.06}>
      {faq.map((f, i) => {
        const isOpen = open === i;
        return (
          <StaggerItem key={f.q}>
            <div className={cx("rounded-2xl ring-1 backdrop-blur transition-colors duration-300", isOpen ? "bg-white/[0.08] ring-brand-300/40" : "bg-white/[0.03] ring-white/10 hover:bg-white/[0.06]")}>
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : i)}
                className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left font-medium text-white"
              >
                {f.q}
                <motion.span animate={{ rotate: isOpen ? 45 : 0 }} transition={{ type: "spring", stiffness: 300, damping: 20 }}
                  className={cx("flex size-7 shrink-0 items-center justify-center rounded-full ring-1", isOpen ? "bg-brand-300 text-brand-950 ring-brand-300" : "text-brand-100/70 ring-white/15")}>
                  <Plus className="size-4" />
                </motion.span>
              </button>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={reduce ? undefined : { height: 0, opacity: 0 }}
                    transition={{ duration: 0.4, ease: EASE }}
                    className="overflow-hidden"
                  >
                    <p className="max-w-[65ch] px-6 pb-5 leading-relaxed text-brand-100/75">{f.a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </StaggerItem>
        );
      })}
    </Stagger>
  );
}
