/** Cover for a course or resource: the uploaded image, or a coloured panel with the title when there is none. */
import { cx } from "./ui";

const GRADIENTS = ["from-violet-500 to-indigo-800", "from-brand-500 to-brand-900", "from-sky-500 to-blue-900",
  "from-emerald-500 to-teal-900", "from-amber-600 to-rose-900"];

function gradient(seed: string) {
  let n = 0;
  for (const ch of seed) n = (n + ch.charCodeAt(0)) % GRADIENTS.length;
  return GRADIENTS[n];
}

export default function CoverImage({ src, title, seed, kicker = "BENCHMARK EDUCATION", small, className }:
  { src: string | null; title: string; seed: string; kicker?: string; small?: boolean; className?: string }) {
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element -- served by the API with its own access checks
    return <img src={src} alt="" className={cx("h-full w-full object-cover", className)} />;
  }
  return (
    <div className={cx("flex h-full w-full flex-col justify-between bg-gradient-to-br text-white", gradient(seed), small ? "p-2.5" : "p-5", className)}>
      <span className={cx("tracking-wide opacity-80", small ? "text-[8px]" : "text-[10px]")}>{kicker}</span>
      <strong className={cx("leading-tight [overflow-wrap:anywhere]", small ? "text-xs" : "text-xl")}>{title}</strong>
    </div>
  );
}
