"use client";

import { Headphones, Mic, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Logo } from "@/components/AppShell";
import { Button, ErrorNote } from "@/components/ui";
import { api, type User } from "@/lib/api";

const DEMO = [
  { label: "Student (with history)", email: "priya@example.com" },
  { label: "Student (new)", email: "arjun@example.com" },
  { label: "Assessor", email: "assessor@example.com" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e?: FormEvent, override?: { email: string; password: string }) => {
    e?.preventDefault();
    setLoading(true);
    setError("");
    try {
      const u = await api<User>("/auth/login", { method: "POST", json: override ?? { email, password } });
      router.replace(u.role === "assessor" ? "/admin" : "/dashboard");
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-brand-950 p-12 text-white lg:flex">
        <Logo light />
        <div className="max-w-md">
          <h1 className="text-4xl font-semibold leading-tight tracking-tight">Practise the CCL the way you&apos;ll sit it.</h1>
          <p className="mt-4 text-brand-100/80">Real exam flow, segment by segment. Instant, specific feedback on what you actually said.</p>
          <ul className="mt-10 space-y-4 text-sm text-brand-100">
            <li className="flex gap-3"><Headphones className="size-5 shrink-0 text-brand-300" /> Each segment plays once. One repeat, just like the exam.</li>
            <li className="flex gap-3"><Mic className="size-5 shrink-0 text-brand-300" /> Record your interpretation after the chime.</li>
            <li className="flex gap-3"><ShieldCheck className="size-5 shrink-0 text-brand-300" /> Scored out of 90 against the pass rules.</li>
          </ul>
        </div>
        <p className="text-xs text-brand-200/60">Demo build. All dialogues are original practice material.</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Use your Benchmark account.</p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Email</span>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username"
                className="mt-1 block h-10 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20" />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">Password</span>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
                className="mt-1 block h-10 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20" />
            </label>
            {error && <ErrorNote>{error}</ErrorNote>}
            <Button type="submit" loading={loading} className="w-full">Sign in</Button>
          </form>

          <div className="mt-10 rounded-xl border border-dashed border-slate-300 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Demo accounts · password demo1234</p>
            <div className="mt-3 space-y-2">
              {DEMO.map((d) => (
                <button key={d.email} onClick={() => submit(undefined, { email: d.email, password: "demo1234" })}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-100">
                  <span className="font-medium">{d.label}</span>
                  <span className="text-xs text-slate-500">{d.email}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
