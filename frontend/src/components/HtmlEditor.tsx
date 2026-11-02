"use client";

import { Bold, Heading2, Italic, Link2, List, ListOrdered } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { cx, inputClass } from "./ui";

const TOOLS = [
  { icon: Bold, title: "Bold", before: "<strong>", after: "</strong>", fallback: "bold text" },
  { icon: Italic, title: "Italic", before: "<em>", after: "</em>", fallback: "italic text" },
  { icon: Heading2, title: "Heading", before: "<h2>", after: "</h2>\n", fallback: "Heading" },
  { icon: List, title: "Bulleted list", before: "<ul>\n  <li>", after: "</li>\n</ul>\n", fallback: "List item" },
  { icon: ListOrdered, title: "Numbered list", before: "<ol>\n  <li>", after: "</li>\n</ol>\n", fallback: "List item" },
];
const toolClass = "rounded p-1.5 text-slate-500 hover:bg-white hover:text-ink";

/** HTML text field for the course and lesson editors: buttons wrap the selected text in tags, and the preview shows
 * exactly what the server will store after sanitising. */
export default function HtmlEditor({ label, value, onChange, heightClass = "h-48", placeholder, previewClass }:
  { label: string; value: string; onChange: (html: string) => void; heightClass?: string; placeholder?: string; previewClass?: string }) {
  const area = useRef<HTMLTextAreaElement>(null);
  const [preview, setPreview] = useState(value);

  useEffect(() => {
    const t = setTimeout(() => {
      api<{ html: string }>("/admin/sanitize-html", { method: "POST", json: { html: value } }).then((r) => setPreview(r.html)).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [value]);

  const wrap = (before: string, after: string, fallback: string) => {
    const el = area.current;
    if (!el) return;
    const { selectionStart: start, selectionEnd: end } = el;
    const text = value.slice(start, end) || fallback;
    onChange(value.slice(0, start) + before + text + after + value.slice(end));
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(start + before.length, start + before.length + text.length); });
  };
  const addLink = () => {
    const url = prompt("Link address", "https://");
    if (url && url !== "https://") wrap(`<a href="${url.replaceAll('"', "%22")}">`, "</a>", "link text");
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <label className="block"><span className="text-sm font-medium text-slate-700">{label}</span>
        <div className="mt-1 flex gap-0.5 rounded-t-lg border border-b-0 border-slate-200 bg-slate-50 p-1">
          {TOOLS.map((t) => {
            const Icon = t.icon;
            return <button key={t.title} type="button" title={t.title} aria-label={t.title} onClick={() => wrap(t.before, t.after, t.fallback)} className={toolClass}><Icon className="size-4" /></button>;
          })}
          <button type="button" title="Link" aria-label="Link" onClick={addLink} className={toolClass}><Link2 className="size-4" /></button>
        </div>
        <textarea ref={area} className={cx(inputClass, "mt-0 rounded-t-none py-2 font-mono text-xs", heightClass)} value={value} placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)} /></label>
      <div><span className="text-sm font-medium text-slate-700">Preview (sanitised)</span>
        <div className={cx("mt-1 overflow-auto rounded-lg border border-slate-200 p-3 text-sm", heightClass)}>
          <div className={cx("lesson-html", previewClass)} dangerouslySetInnerHTML={{ __html: preview }} /></div></div>
    </div>
  );
}
