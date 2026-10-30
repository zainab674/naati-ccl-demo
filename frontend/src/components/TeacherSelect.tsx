"use client";

import { useEffect, useState } from "react";

import { inputClass } from "@/components/ui";
import { api } from "@/lib/api";

export type Teacher = { id: string; name: string; email: string; is_active: boolean; students: number };

/** Teachers for admins' pickers (the endpoint is admins only, so teachers get an empty list). */
export function useTeachers(enabled: boolean) {
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  useEffect(() => {
    if (enabled) api<Teacher[]>("/admin/teachers").then(setTeachers).catch(() => {});
  }, [enabled]);
  return teachers;
}

export default function TeacherSelect({ teachers, value, onChange, label = "Teacher", none = "No teacher", className }:
  { teachers: Teacher[]; value: string; onChange: (id: string) => void; label?: string; none?: string; className?: string }) {
  return (
    <label className={className ?? "block"}><span className="text-sm font-medium text-slate-700">{label}</span>
      <select className={inputClass} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{none}</option>
        {teachers.map((t) => <option key={t.id} value={t.id}>{t.name}{t.is_active ? "" : " (deactivated)"}</option>)}
      </select></label>
  );
}
