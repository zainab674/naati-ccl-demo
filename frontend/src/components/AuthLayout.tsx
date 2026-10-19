import { Headphones, Mic, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "./Logo";

export default function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-brand-950 p-12 text-white lg:flex">
        <Link href="/"><Logo light /></Link>
        <div className="max-w-md">
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">Practise the CCL the way you&apos;ll sit it.</h1>
          <p className="mt-4 text-brand-100/80">English and Filipino dialogues, segment by segment, with feedback on every deduction.</p>
          <ul className="mt-10 space-y-4 text-sm text-brand-100">
            <li className="flex gap-3"><Headphones className="size-5 shrink-0 text-brand-300" /> The same flow as the NAATI practice test.</li>
            <li className="flex gap-3"><Mic className="size-5 shrink-0 text-brand-300" /> Record your interpretation after the chime.</li>
            <li className="flex gap-3"><ShieldCheck className="size-5 shrink-0 text-brand-300" /> Estimated score out of 90 against the pass rules.</li>
          </ul>
        </div>
        <p className="text-xs text-brand-200/60">Scores are estimates to guide your practice, not official NAATI results.</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Link href="/"><Logo /></Link></div>
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
