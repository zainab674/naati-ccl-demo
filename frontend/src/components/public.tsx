import { Check, Star } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { Faq, PlanContent, PublicPlan, Review } from "@/lib/content";
import { cx } from "./cx";
import { Logo } from "./Logo";
import { BrandName } from "./Theme";

const btn = "inline-flex h-11 items-center justify-center gap-2 rounded-lg px-5 text-sm font-semibold transition-colors";
export const btnPrimary = cx(btn, "bg-brand-600 text-white hover:bg-brand-700");
export const btnSecondary = cx(btn, "bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50");

export function PublicHeader({ dark }: { dark?: boolean }) {
  const link = dark ? "hover:text-white" : "hover:text-ink";
  return (
    <header className={cx("sticky top-0 z-30 border-b backdrop-blur-xl", dark ? "border-white/10 bg-brand-950/60" : "border-brand-100 bg-brand-50/85")}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="Home"><Logo compact light={dark} /></Link>
        <nav className={cx("hidden items-center gap-6 text-sm transition-colors md:flex", dark ? "text-brand-100/70" : "text-slate-600")}>
          <Link href="/self-study" className={link}>Self-Study</Link>
          <Link href="/coaching" className={link}>Coaching</Link>
          <Link href="/pricing" className={link}>Pricing</Link>
          <Link href="/#faq" className={link}>FAQ</Link>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login" className={cx("whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium", dark ? "text-brand-50/90 hover:bg-white/10" : "text-slate-700 hover:bg-slate-100")}>Sign in</Link>
          <Link href="/signup" className={cx(btnPrimary, "h-9 whitespace-nowrap px-4")}>Start free</Link>
        </div>
      </div>
    </header>
  );
}

export function PublicFooter({ disclaimer, dark }: { disclaimer?: string; dark?: boolean }) {
  const link = dark ? "hover:text-white" : "hover:text-ink";
  return (
    <footer className={cx("border-t", dark ? "border-white/10 bg-black/20" : "border-brand-100 bg-brand-100/50")}>
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-start sm:justify-between sm:px-6">
        <div className="max-w-sm">
          <Logo light={dark} />
          {disclaimer && <p className={cx("mt-3 text-xs", dark ? "text-brand-100/60" : "text-slate-500")}>{disclaimer}</p>}
        </div>
        <nav className={cx("flex flex-wrap gap-x-6 gap-y-2 text-sm", dark ? "text-brand-100/70" : "text-slate-600")}>
          <Link href="/self-study" className={link}>Self-Study</Link>
          <Link href="/coaching" className={link}>Coaching</Link>
          <Link href="/pricing" className={link}>Pricing</Link>
          <Link href="/terms" className={link}>Terms</Link>
          <Link href="/privacy" className={link}>Privacy</Link>
        </nav>
      </div>
      <div className={cx("border-t py-4 text-center text-xs", dark ? "border-white/10 text-brand-100/50" : "border-brand-100 text-slate-400")}>
        © {new Date().getFullYear()} <BrandName />
      </div>
    </footer>
  );
}

/** `dark` gives the shell the deep brand look used by the landing page; other public pages stay light. */
export function PublicPage({ children, disclaimer, dark }: { children: ReactNode; disclaimer?: string; dark?: boolean }) {
  return (
    <div className={cx("flex min-h-screen flex-col", dark ? "bg-brand-950 text-white" : "bg-brand-50")}>
      <PublicHeader dark={dark} />
      <main className="flex-1">{children}</main>
      <PublicFooter disclaimer={disclaimer} dark={dark} />
    </div>
  );
}

export function Section({ id, title, subtitle, children, muted }: { id?: string; title?: string; subtitle?: string; children: ReactNode; muted?: boolean }) {
  return (
    <section id={id} className={cx("px-4 py-16 sm:px-6 sm:py-20", muted && "bg-slate-50")}>
      <div className="mx-auto max-w-6xl">
        {title && <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h2>}
        {subtitle && <p className="mt-2 max-w-2xl text-slate-600">{subtitle}</p>}
        <div className={title ? "mt-10" : ""}>{children}</div>
      </div>
    </section>
  );
}

/** `glass` is for dark pages: the plain card becomes translucent with light text instead of a white card. */
export function PlanCard({ plan, content, highlight, glass }: { plan?: PublicPlan; content: PlanContent | null; highlight?: boolean; glass?: boolean }) {
  const key = plan?.key ?? "";
  const name = content?.title ?? plan?.name ?? "";
  const contact = !plan || plan.contact_only;
  const onDark = highlight || glass;
  return (
    <div className={cx("flex flex-col rounded-2xl p-7 ring-1",
      highlight ? "bg-brand-950 text-white ring-brand-950" : glass ? "bg-brand-950/80 text-white ring-white/10 backdrop-blur" : "bg-white text-ink ring-slate-200")}>
      <h3 className="text-lg font-semibold">{name}</h3>
      {content?.tagline && <p className={cx("mt-1 text-sm", onDark ? "text-brand-100/80" : "text-slate-500")}>{content.tagline}</p>}
      <div className="mt-5 text-2xl font-semibold">
        {plan?.price_display || <span className={cx("text-base font-medium", onDark ? "text-brand-100" : "text-slate-500")}>{contact ? "Contact us for pricing" : "See price at checkout"}</span>}
      </div>
      <ul className="mt-6 flex-1 space-y-3 text-sm">
        {(content?.included ?? plan?.features ?? []).map((f) => (
          <li key={f} className="flex gap-2"><Check className={cx("mt-0.5 size-4 shrink-0", onDark ? "text-brand-300" : "text-brand-600")} />{f}</li>
        ))}
      </ul>
      <div className="mt-8 flex flex-wrap gap-3">
        <EnrolButton planKey={key} contact={contact} contactEmail={content?.contact_email} label={content?.cta} light={onDark} />
        <Link href={`/${key}`} className={cx("inline-flex h-11 items-center text-sm font-medium hover:underline", onDark ? "text-brand-100" : "text-brand-700")}>Details</Link>
      </div>
    </div>
  );
}

export function EnrolButton({ planKey, contact, contactEmail, label, light }: { planKey: string; contact: boolean; contactEmail?: string; label?: string; light?: boolean }) {
  const cls = light ? cx(btn, "bg-white text-brand-950 hover:bg-brand-50") : btnPrimary;
  if (contact) {
    return contactEmail
      ? <a href={`mailto:${contactEmail}`} className={cls}>{label || "Contact us"}</a>
      : <span className={cx("inline-flex h-11 items-center text-sm", light ? "text-brand-100" : "text-slate-600")}>Contact <BrandName /> to enrol</span>;
  }
  return <Link href={`/enrol/${planKey}`} className={cls}>{label || "Enrol now"}</Link>;
}

export function Reviews({ reviews }: { reviews: Review[] }) {
  if (!reviews.length) return null;
  return (
    <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
      {reviews.map((r, i) => (
        <figure key={i} className="rounded-xl bg-white p-6 text-ink ring-1 ring-slate-200">
          {r.placeholder && <div className="mb-3 inline-block rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-800">Placeholder</div>}
          {r.rating ? <div className="flex gap-0.5 text-amber-500">{Array.from({ length: r.rating }).map((_, j) => <Star key={j} className="size-4 fill-current" />)}</div> : null}
          <blockquote className="mt-3 text-sm text-slate-700">&ldquo;{r.text}&rdquo;</blockquote>
          <figcaption className="mt-4 text-sm font-medium">{r.name}</figcaption>
        </figure>
      ))}
    </div>
  );
}

export function FaqList({ faq }: { faq: Faq }) {
  return (
    <div className="divide-y divide-slate-200 rounded-xl bg-white ring-1 ring-slate-200">
      {faq.map((f) => (
        <details key={f.q} className="group px-6 py-4">
          <summary className="cursor-pointer list-none font-medium marker:hidden">
            <span className="flex items-center justify-between gap-4">{f.q}<span className="text-slate-400 transition-transform group-open:rotate-45">+</span></span>
          </summary>
          <p className="mt-3 text-sm text-slate-600">{f.a}</p>
        </details>
      ))}
    </div>
  );
}
