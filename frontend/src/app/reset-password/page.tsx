"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import AuthLayout from "@/components/AuthLayout";
import { Button, ErrorNote, Field } from "@/components/ui";
import { api, type User } from "@/lib/api";

function ResetForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError("The passwords don't match."); return; }
    setLoading(true);
    setError("");
    try {
      const u = await api<User>("/auth/reset-password", { method: "POST", json: { token, password } });
      router.replace(u.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  if (!token) {
    return <ErrorNote>This link is missing its token. <Link href="/forgot-password" className="underline">Request a new link</Link>.</ErrorNote>;
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="New password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
      <Field label="Confirm new password" type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
      {error && <ErrorNote>{error}</ErrorNote>}
      <Button type="submit" loading={loading} className="w-full">Set new password</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthLayout title="Choose a new password">
      <Suspense><ResetForm /></Suspense>
    </AuthLayout>
  );
}
