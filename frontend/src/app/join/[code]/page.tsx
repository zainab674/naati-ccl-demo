"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AuthLayout from "@/components/AuthLayout";
import { Button, ErrorNote, LinkButton, Spinner } from "@/components/ui";
import { api, type User } from "@/lib/api";

/** A teacher's class link. New students sign up into the class; signed-in students join it. */
export default function JoinClass() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();
  const [teacher, setTeacher] = useState<string | null>(null);
  const [me, setMe] = useState<User | null | undefined>(undefined);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ teacher: string }>(`/public/join/${encodeURIComponent(code)}`).then((r) => setTeacher(r.teacher))
      .catch((e) => setError(e.message));
    api<User>("/me", { noAuthRedirect: true }).then(setMe).catch(() => setMe(null));
  }, [code]);

  const join = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/me/join", { method: "POST", json: { code } });
      router.replace("/dashboard");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  if (error && !teacher) {
    return (
      <AuthLayout title="Class link not valid" subtitle="This link has expired or been replaced. Ask your teacher for a new one.">
        <LinkButton href="/signup" variant="secondary">Create an account without a class</LinkButton>
      </AuthLayout>
    );
  }
  if (!teacher || me === undefined) return <Spinner />;

  const next = encodeURIComponent(`/join/${code}`);
  return (
    <AuthLayout title={`Join ${teacher}'s class`}
      subtitle="Your teacher will see your practice and mock test results, and you will see the courses they prepare for you.">
      <div className="space-y-4">
        {me ? (me.role !== "student" ? <ErrorNote>You are signed in as staff. Sign out to join as a student.</ErrorNote> : (
          me.teacher === teacher ? <>
            <p className="text-sm text-slate-600">You are already in {teacher}&apos;s class.</p>
            <LinkButton href="/dashboard" className="w-full">Go to your dashboard</LinkButton>
          </> : <>
            <p className="text-sm text-slate-600">Signed in as {me.email}.</p>
            <Button onClick={join} loading={busy} className="w-full">Join the class</Button>
          </>)) : <>
          <LinkButton href={`/signup?teacher=${encodeURIComponent(code)}`} className="w-full">Create an account</LinkButton>
          <LinkButton href={`/login?next=${next}`} variant="secondary" className="w-full">I already have an account</LinkButton>
        </>}
        {error && <ErrorNote>{error}</ErrorNote>}
      </div>
    </AuthLayout>
  );
}
