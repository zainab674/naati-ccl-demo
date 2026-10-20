"use client";

import { useEffect, useState } from "react";

import { fetchLanguages, type Language } from "@/lib/api";
import { useUser } from "./AppShell";
import { inputClass } from "./ui";

/**
 * Language filter for student lists. "" = the student's own language (the API default), "all" = every language,
 * otherwise a language code.
 */
export default function LanguagePicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { user } = useUser();
  const [languages, setLanguages] = useState<Language[]>([]);
  useEffect(() => { fetchLanguages().then(setLanguages).catch(() => {}); }, []);
  const mine = languages.find((l) => l.code === user.language);
  return (
    <select aria-label="Language" value={value} onChange={(e) => onChange(e.target.value)} className={`${inputClass} mt-0 !w-56`}>
      {mine ? <option value="">{mine.name} (my language)</option> : <option value="">All languages</option>}
      {mine && <option value="all">All languages</option>}
      {languages.filter((l) => l.code !== user.language).map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
    </select>
  );
}
