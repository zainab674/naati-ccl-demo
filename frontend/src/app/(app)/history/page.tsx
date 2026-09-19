"use client";

import { useEffect, useState } from "react";

import { AttemptList } from "@/components/attempts";
import { Card, LinkButton, PageHeader, Spinner } from "@/components/ui";
import { api, type AttemptSummary } from "@/lib/api";

export default function History() {
  const [items, setItems] = useState<AttemptSummary[] | null>(null);
  useEffect(() => { api<AttemptSummary[]>("/attempts").then(setItems); }, []);
  return (
    <div>
      <PageHeader title="My attempts" subtitle="Every practice dialogue and mock test you've taken, with feedback." />
      <Card>
        {!items ? <Spinner /> : items.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-14 text-sm text-slate-500">
            You haven&apos;t attempted anything yet.
            <LinkButton href="/library">Browse dialogues</LinkButton>
          </div>
        ) : <AttemptList items={items} />}
      </Card>
    </div>
  );
}
