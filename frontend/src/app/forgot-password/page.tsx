"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import AuthLayout from "@/components/AuthLayout";
import { Button, ErrorNote, Field, SuccessNote } from "@/components/ui";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/auth/forgot-password", { method: "POST", json: { email } });
      setSent(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to choose a new password.">
      {sent ? (
        <SuccessNote>If an account exists for {email}, a reset link is on its way. The link expires in 60 minutes.</SuccessNote>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          {error && <ErrorNote>{error}</ErrorNote>}
          <Button type="submit" loading={loading} className="w-full">Send reset link</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm"><Link href="/login" className="text-brand-600 hover:underline">Back to sign in</Link></p>
    </AuthLayout>
  );
}
