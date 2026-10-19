import { notFound } from "next/navigation";

import { PublicPage, Section } from "@/components/public";
import { getContent, type LegalContent } from "@/lib/content";

export default async function LegalPage({ contentKey }: { contentKey: "terms" | "privacy" }) {
  const c = await getContent<LegalContent>(contentKey);
  if (!c) notFound();
  return (
    <PublicPage>
      <Section>
        <article className="mx-auto max-w-3xl">
          <h1 className="text-3xl font-semibold tracking-tight">{c.title}</h1>
          {c.updated && <p className="mt-2 text-sm text-slate-500">Last updated {c.updated}</p>}
          {c.draft && (
            <div className="mt-6 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200">
              Draft: to be reviewed and replaced by Benchmark Education before launch.
            </div>
          )}
          {c.sections.map((s) => (
            <section key={s.heading} className="mt-8">
              <h2 className="text-lg font-semibold">{s.heading}</h2>
              <p className="mt-2 whitespace-pre-line text-slate-700">{s.body}</p>
            </section>
          ))}
        </article>
      </Section>
    </PublicPage>
  );
}
