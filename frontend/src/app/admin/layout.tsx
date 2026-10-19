import type { Metadata } from "next";

import AppShell from "@/components/AppShell";

export const metadata: Metadata = { title: "Admin", robots: { index: false } };

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return <AppShell admin>{children}</AppShell>;
}
