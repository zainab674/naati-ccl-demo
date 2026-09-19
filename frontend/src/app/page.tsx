"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui";
import { api, type User } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    api<User>("/me")
      .then((u) => router.replace(u.role === "assessor" ? "/admin" : "/dashboard"))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <Spinner />;
}
