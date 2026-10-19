"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import AuthLayout from "@/components/AuthLayout";
import { Button, ErrorNote, Field } from "@/components/ui";
import { api, safeNext, type User } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const u = await api<User>("/auth/login", { method: "POST", json: { email, password } });
      router.replace(safeNext(params.get("next"), u.role === "admin" ? "/admin" : "/dashboard"));
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
      <Field label="Password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
      <div className="text-right text-sm"><Link href="/forgot-password" className="text-brand-600 hover:underline">Forgot password?</Link></div>
      {error && <ErrorNote>{error}</ErrorNote>}
      <Button type="submit" loading={loading} className="w-full">Sign in</Button>
      <p className="text-center text-sm text-slate-500">New here? <Link href="/signup" className="font-medium text-brand-600 hover:underline">Create an account</Link></p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthLayout title="Sign in" subtitle="Welcome back.">
      <Suspense><LoginForm /></Suspense>
    </AuthLayout>
  );
}
