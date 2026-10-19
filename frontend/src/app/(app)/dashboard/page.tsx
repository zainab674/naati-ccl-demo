"use client";

import { useUser } from "@/components/AppShell";
import { PageHeader } from "@/components/ui";

export default function DashboardPage() {
  const { user } = useUser();
  return <PageHeader title={`Welcome, ${user.first_name}`} subtitle="Your practice dashboard." />;
}
