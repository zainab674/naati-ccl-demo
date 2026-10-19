"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui";
import { api, type User } from "@/lib/api";

// Replaced by the public home page in task 1.5.
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    api<User>("/me")
      .then((u) => router.replace(u.role === "admin" ? "/admin" : "/dashboard"))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <Spinner />;
}
