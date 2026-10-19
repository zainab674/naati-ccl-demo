"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { ErrorNote } from "@/components/ui";
import { api, ApiError, type User } from "@/lib/api";

/** Enrol button target: signed-out visitors sign up first, then go straight to Stripe Checkout. */
export default function EnrolPage() {
  const { plan } = useParams<{ plan: string }>();
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const me = await api<User>("/me", { noAuthRedirect: true });
        if (me.has_active_plan && me.role !== "admin") { router.replace("/dashboard"); return; }
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          router.replace(`/signup?next=${encodeURIComponent(`/enrol/${plan}`)}`);
          return;
        }
      }
      try {
        const r = await api<{ url: string }>("/billing/checkout", { method: "POST", json: { plan_key: plan } });
        window.location.assign(r.url);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [plan, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <Logo />
      {error ? (
        <div className="max-w-md space-y-4 text-center">
          <ErrorNote>{error}</ErrorNote>
          <Link href="/pricing" className="text-sm text-brand-600 hover:underline">Back to pricing</Link>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="size-4 animate-spin" /> Taking you to secure checkout…</div>
      )}
    </div>
  );
}
