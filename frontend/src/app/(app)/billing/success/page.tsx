"use client";

import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Card, LinkButton } from "@/components/ui";
import { api, type User } from "@/lib/api";

/** Stripe redirects here after checkout. Access unlocks when the webhook arrives, usually within seconds. */
export default function BillingSuccessPage() {
  const { refresh } = useUser();
  const [active, setActive] = useState(false);
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      for (let i = 0; i < 30 && alive; i++) {
        const u = await api<User>("/me").catch(() => null);
        if (u?.has_active_plan) { setActive(true); refresh(); return; }
        await new Promise((r) => setTimeout(r, 2000));
      }
      if (alive) setTimedOut(true);
    })();
    return () => { alive = false; };
  }, [refresh]);

  return (
    <Card className="mx-auto max-w-lg p-10 text-center">
      {active ? (
        <>
          <CheckCircle2 className="mx-auto size-10 text-emerald-600" />
          <h1 className="mt-4 text-xl font-semibold">Payment received. Your plan is active.</h1>
          <p className="mt-2 text-sm text-slate-500">A receipt has been emailed to you.</p>
          <LinkButton href="/dashboard" className="mt-6">Go to your dashboard</LinkButton>
        </>
      ) : (
        <>
          <Loader2 className="mx-auto size-8 animate-spin text-brand-500" />
          <h1 className="mt-4 text-xl font-semibold">Confirming your payment…</h1>
          <p className="mt-2 text-sm text-slate-500">
            {timedOut ? "This is taking longer than usual. Your access will unlock automatically; you can check your account page in a minute."
              : "This usually takes a few seconds."}
          </p>
          {timedOut && <LinkButton href="/account" variant="secondary" className="mt-6">Account page</LinkButton>}
        </>
      )}
    </Card>
  );
}
