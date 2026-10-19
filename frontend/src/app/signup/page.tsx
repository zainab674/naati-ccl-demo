"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type ChangeEvent, type FormEvent, Suspense, useState } from "react";

import AuthLayout from "@/components/AuthLayout";
import { Button, ErrorNote, Field } from "@/components/ui";
import { api, safeNext } from "@/lib/api";

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", password: "", target_exam_date: "" });
  const [accept, setAccept] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof f) => (e: ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/auth/signup", {
        method: "POST",
        json: { ...f, target_exam_date: f.target_exam_date || null, accept_terms: accept },
      });
      router.replace(safeNext(params.get("next"), "/dashboard"));
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="First name" required value={f.first_name} onChange={set("first_name")} autoComplete="given-name" />
        <Field label="Last name" value={f.last_name} onChange={set("last_name")} autoComplete="family-name" />
      </div>
      <Field label="Email" type="email" required value={f.email} onChange={set("email")} autoComplete="email" />
      <Field label="Password" type="password" required minLength={8} value={f.password} onChange={set("password")}
        autoComplete="new-password" hint="At least 8 characters." />
      <Field label="Target exam date (optional)" type="date" value={f.target_exam_date} onChange={set("target_exam_date")} />
      <label className="flex items-start gap-2 text-sm text-slate-600">
        <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} required className="mt-0.5 accent-brand-600" />
        <span>I agree to the <Link href="/terms" className="text-brand-600 hover:underline">Terms</Link> and{" "}
          <Link href="/privacy" className="text-brand-600 hover:underline">Privacy Policy</Link>.</span>
      </label>
      {error && <ErrorNote>{error}</ErrorNote>}
      <Button type="submit" loading={loading} className="w-full">Create account</Button>
      <p className="text-center text-sm text-slate-500">Already have an account? <Link href="/login" className="font-medium text-brand-600 hover:underline">Sign in</Link></p>
    </form>
  );
}

export default function SignupPage() {
  return (
    <AuthLayout title="Create your account" subtitle="Start with the free introduction course and practice dialogue.">
      <Suspense><SignupForm /></Suspense>
    </AuthLayout>
  );
}
