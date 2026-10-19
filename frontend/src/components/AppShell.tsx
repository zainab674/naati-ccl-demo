"use client";

import {
  BookOpen, ClipboardCheck, GraduationCap, History, LayoutDashboard, LogOut, Menu, Upload, Users, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { api, type User } from "@/lib/api";
import { Logo } from "./Logo";
import { cx, Spinner } from "./ui";

export { Logo };

const UserCtx = createContext<{ user: User; refresh: () => Promise<unknown> } | null>(null);
export const useUser = () => useContext(UserCtx)!;

type NavItem = { href: string; label: string; icon: typeof BookOpen };

const STUDENT_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dialogues", label: "Practice dialogues", icon: BookOpen },
  { href: "/mock-tests", label: "Mock tests", icon: ClipboardCheck },
  { href: "/courses", label: "Courses", icon: GraduationCap },
  { href: "/attempts", label: "My attempts", icon: History },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/students", label: "Students", icon: Users },
  { href: "/admin/dialogues", label: "Dialogues", icon: BookOpen },
  { href: "/admin/mock-tests", label: "Mock tests", icon: ClipboardCheck },
  { href: "/admin/courses", label: "Courses", icon: GraduationCap },
  { href: "/admin/imports", label: "CSV import", icon: Upload },
];

export default function AppShell({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  const load = useCallback(() => api<User>("/me").then((u) => {
    if (admin && u.role !== "admin") { router.replace("/dashboard"); return; }
    setUser(u);
  }), [admin, router]);
  useEffect(() => { load().catch(() => {}); }, [load]);

  if (!user) return <Spinner />;
  const nav = admin ? ADMIN_NAV : STUDENT_NAV;

  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  };

  const sidebar = (
    <nav className="flex h-full flex-col bg-brand-950 px-3 py-5">
      <div className="px-2 pb-6"><Link href="/"><Logo light /></Link></div>
      <div className="flex-1 space-y-0.5">
        {nav.map((item) => {
          const active = pathname === item.href || (item.href !== "/admin" && pathname.startsWith(item.href + "/"));
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} onClick={() => setOpen(false)}
              className={cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active ? "bg-white/10 font-medium text-white" : "text-brand-100/80 hover:bg-white/5 hover:text-white")}>
              <Icon className="size-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
            </Link>
          );
        })}
        {user.role === "admin" && (
          <Link href={admin ? "/dashboard" : "/admin"} className="mt-4 flex items-center gap-3 rounded-lg px-3 py-2 text-xs text-brand-200 hover:text-white">
            {admin ? "Student view" : "Admin"}
          </Link>
        )}
      </div>
      <div className="border-t border-white/10 px-2 pt-4">
        <div className="truncate text-sm font-medium text-white">{user.name}</div>
        <div className="truncate text-xs text-brand-200/70">{user.email}</div>
        <Link href="/account" className="mt-3 block text-xs text-brand-200 hover:text-white">Account and billing</Link>
        <button onClick={logout} className="mt-2 flex items-center gap-2 text-xs text-brand-200 hover:text-white">
          <LogOut className="size-3.5" /> Sign out
        </button>
      </div>
    </nav>
  );

  return (
    <UserCtx.Provider value={{ user, refresh: load }}>
      <div className="flex min-h-screen">
        <aside className="fixed inset-y-0 left-0 hidden w-60 lg:block">{sidebar}</aside>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
            <aside className="absolute inset-y-0 left-0 w-64">{sidebar}</aside>
          </div>
        )}
        <div className="min-w-0 flex-1 lg:pl-60">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:hidden">
            <button onClick={() => setOpen(!open)} aria-label="Menu" className="rounded p-1.5 hover:bg-slate-100">
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
            <Logo />
          </header>
          <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8">{children}</main>
        </div>
      </div>
    </UserCtx.Provider>
  );
}
