"use client";

import { Loader2, X } from "lucide-react";
import Link from "next/link";
import { type ButtonHTMLAttributes, type ReactNode, useEffect } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger";
const variants: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm disabled:bg-brand-600/50",
  secondary: "bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50 shadow-sm disabled:opacity-50",
  ghost: "text-slate-600 hover:bg-slate-100 disabled:opacity-50",
  danger: "bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50",
};

export function Button({
  variant = "primary", size = "md", loading, className, children, ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" | "lg"; loading?: boolean }) {
  const sizes = { sm: "h-8 px-3 text-sm", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-base" };
  return (
    <button
      className={cx("inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed",
        variants[variant], sizes[size], className)}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

export function LinkButton({ href, variant = "primary", className, children }:
  { href: string; variant?: Variant; className?: string; children: ReactNode }) {
  return (
    <Link href={href} className={cx("inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors",
      variants[variant], className)}>
      {children}
    </Link>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx("rounded-xl bg-white ring-1 ring-slate-200/80 shadow-[0_1px_2px_rgba(15,28,34,0.04)]", className)}>{children}</div>;
}

export function Badge({ tone = "slate", children, className }:
  { tone?: "slate" | "green" | "red" | "amber" | "brand" | "violet"; children: ReactNode; className?: string }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    red: "bg-rose-50 text-rose-700 ring-rose-600/20",
    amber: "bg-amber-50 text-amber-800 ring-amber-600/20",
    brand: "bg-brand-50 text-brand-700 ring-brand-600/20",
    violet: "bg-violet-50 text-violet-700 ring-violet-600/20",
  };
  return <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-transparent", tones[tone], className)}>{children}</span>;
}

export function DifficultyBadge({ level }: { level: string }) {
  const tone = level === "Easy" ? "green" : level === "Hard" ? "red" : "amber";
  return <Badge tone={tone}>{level}</Badge>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone = severity === "critical" ? "red" : severity === "major" ? "amber" : "slate";
  return <Badge tone={tone} className="capitalize">{severity}</Badge>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
      <Loader2 className="size-4 animate-spin" /> {label ?? "Loading"}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div className={cx("max-h-[90vh] w-full overflow-y-auto rounded-xl bg-white p-6 shadow-xl", wide ? "max-w-3xl" : "max-w-lg")} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close"><X className="size-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200">{children}</div>;
}

export function ScoreRing({ score, max, passed, size = 132 }: { score: number; max: number; passed: boolean; size?: number }) {
  const r = size / 2 - 9;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, score / max));
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={9} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={9} strokeLinecap="round"
          stroke={passed ? "#059669" : "#e11d48"} strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
          style={{ transition: "stroke-dashoffset 0.8s ease" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums">{score}</span>
        <span className="text-xs text-slate-500">out of {max}</span>
      </div>
    </div>
  );
}
