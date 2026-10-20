"use client";

import { cx } from "./cx";
import { useTheme } from "./Theme";

export function Logo({ light, compact }: { light?: boolean; compact?: boolean }) {
  const t = useTheme();
  return (
    <div className="flex items-center gap-2.5">
      {t.logo_url
        // eslint-disable-next-line @next/next/no-img-element -- admin-uploaded logo served by the API
        ? <img src={t.logo_url} alt="" className="size-8 rounded-lg object-contain" />
        : <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">{t.name.trim().charAt(0).toUpperCase() || "B"}</div>}
      <div className={cx("leading-tight", compact && "hidden sm:block")}>
        <div className={cx("text-sm font-semibold", light ? "text-white" : "text-ink")}>{t.name}</div>
        {t.tagline && <div className={cx("text-[11px] font-medium tracking-wide", light ? "text-brand-200" : "text-brand-600")}>{t.tagline}</div>}
      </div>
    </div>
  );
}
