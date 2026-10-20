"use client";

import { Download, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge, Card, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { fileSize, type ResourceDetail } from "@/lib/resources";

export default function ResourcePage() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<ResourceDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<ResourceDetail>(`/resources/${id}`).then(setR).catch((e) => setError(e.message)); }, [id]);
  if (error) return <ErrorNote>{error} <Link href="/resources" className="underline">Back to the learning hub</Link></ErrorNote>;
  if (!r) return <Spinner />;

  const ct = r.content_type;
  return (
    <>
      <PageHeader title={r.title} subtitle={<Link href="/resources" className="text-brand-600 hover:underline">Learning hub</Link>} />
      <div className="mb-4 flex flex-wrap gap-1.5">
        <Badge>{r.type}</Badge>
        {r.language_name && <Badge tone="violet">{r.language_name}</Badge>}
        {r.topic && <Badge>{r.topic}</Badge>}
      </div>
      {r.description && <p className="mb-6 max-w-3xl text-slate-700">{r.description}</p>}

      {r.file_url && (
        <Card className="mb-6 overflow-hidden">
          {ct === "application/pdf" && <iframe src={r.file_url} title={r.title} className="h-[75vh] w-full border-0" />}
          {ct.startsWith("audio/") && <div className="p-6"><audio controls preload="metadata" src={r.file_url} className="w-full" /></div>}
          {ct.startsWith("video/") && <video controls preload="metadata" src={r.file_url} className="max-h-[75vh] w-full bg-black" />}
          {ct.startsWith("image/") && (
            // eslint-disable-next-line @next/next/no-img-element -- served by the authenticated API, not next/image
            <img src={r.file_url} alt={r.title} className="mx-auto max-h-[75vh]" />
          )}
          <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-5 py-3 text-sm">
            <span className="text-slate-600">{r.file_name} · {fileSize(r.file_size)}</span>
            <a href={r.file_url} download={r.file_name} className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline"><Download className="size-4" /> Download</a>
          </div>
        </Card>
      )}

      {r.html_content && <Card className="lesson-html mb-6 p-6"><div dir="auto" dangerouslySetInnerHTML={{ __html: r.html_content }} /></Card>}

      {r.external_url && (
        <a href={r.external_url} target="_blank" rel="noopener noreferrer"
          className="inline-flex h-10 items-center gap-2 rounded-lg bg-white px-4 text-sm font-medium text-ink shadow-sm ring-1 ring-slate-200 hover:bg-slate-50">
          <ExternalLink className="size-4" /> Open {r.type === "Link" ? "link" : "resource"}</a>
      )}
    </>
  );
}
