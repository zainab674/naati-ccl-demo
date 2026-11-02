"use client";

import { ImagePlus, Trash2 } from "lucide-react";
import { useState } from "react";

import { api } from "@/lib/api";
import { Button, ErrorNote } from "./ui";

/** Cover image for a course or resource in the admin editors. apiPath is e.g. /admin/courses/<id>/image. */
export default function ImageField<T>({ label, url, apiPath, hint, onSaved }:
  { label: string; url: string | null; apiPath: string; hint?: string; onSaved: (updated: T) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const send = async (init: RequestInit) => {
    setBusy(true);
    setError("");
    try { onSaved(await api<T>(apiPath, init)); }
    catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  const upload = (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    send({ method: "POST", body: fd });
  };

  return (
    <div className="text-sm">
      <span className="font-medium text-slate-700">{label}</span>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- served by the API with its own access checks */}
        {url ? <img src={url} alt="" className="h-24 w-36 rounded-lg object-cover ring-1 ring-slate-200" />
          : <div className="flex h-24 w-36 items-center justify-center rounded-lg bg-slate-50 text-xs text-slate-400 ring-1 ring-slate-200">No image</div>}
        <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg bg-white px-4 font-medium text-ink ring-1 ring-slate-200 hover:bg-slate-50">
          <ImagePlus className="size-4" /> {busy ? "Saving..." : url ? "Replace image" : "Upload image"}
          <input type="file" className="hidden" accept="image/png,image/jpeg,image/webp" disabled={busy}
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
        </label>
        {url && <Button variant="ghost" disabled={busy} onClick={() => send({ method: "DELETE" })}><Trash2 className="size-4" /> Remove</Button>}
      </div>
      <p className="mt-1 text-xs text-slate-500">{hint ?? "PNG, JPEG or WebP, up to 5 MB."}</p>
      {error && <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>}
    </div>
  );
}
