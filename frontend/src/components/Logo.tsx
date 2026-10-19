import { cx } from "./cx";

export function Logo({ light }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">B</div>
      <div className="leading-tight">
        <div className={cx("text-sm font-semibold", light ? "text-white" : "text-ink")}>Benchmark Education</div>
        <div className={cx("text-[11px] font-medium tracking-wide", light ? "text-brand-200" : "text-brand-600")}>NAATI CCL PREP</div>
      </div>
    </div>
  );
}
