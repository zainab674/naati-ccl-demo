import type { LucideIcon } from "lucide-react";

import { Badge, Card } from "./ui";

export default function ComingSoon({ icon: Icon, title, text, points }:
  { icon: LucideIcon; title: string; text: string; points: string[] }) {
  return (
    <div className="mx-auto max-w-2xl py-8">
      <Card className="p-8">
        <div className="flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-xl bg-brand-50"><Icon className="size-5 text-brand-600" /></div>
          <div>
            <h1 className="text-xl font-semibold">{title}</h1>
            <Badge tone="amber">Coming soon</Badge>
          </div>
        </div>
        <p className="mt-5 text-slate-600">{text}</p>
        <ul className="mt-5 space-y-2 text-sm text-slate-600">
          {points.map((p) => <li key={p} className="flex gap-2"><span className="text-brand-500">•</span>{p}</li>)}
        </ul>
        <p className="mt-6 text-xs text-slate-400">Planned module. Not part of this demo build.</p>
      </Card>
    </div>
  );
}
