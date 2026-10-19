"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import ImportReport, { type ImportJob } from "@/components/ImportReport";
import { ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";

const RUNNING = ["Committing", "ProcessingMedia"];

export default function ImportJobPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const j = await api<ImportJob>(`/admin/imports/${id}`);
        if (!alive) return;
        setJob(j);
        if (RUNNING.includes(j.status)) timer = setTimeout(load, 3000);
      } catch (e) { setError((e as Error).message); }
    };
    load();
    return () => { alive = false; clearTimeout(timer); };
  }, [id]);

  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!job) return <Spinner />;
  return (
    <>
      <PageHeader title="Import" subtitle={<>Uploaded {fmtDateTime(job.created_at)} · <Link href="/admin/imports" className="text-brand-600 hover:underline">All imports</Link></>} />
      <ImportReport job={job} />
    </>
  );
}
