"use client";

import {
  BookOpen, CalendarDays, ClipboardCheck, FileAudio, Flag, GraduationCap, History, LayoutDashboard, LogOut,
  Menu, MessagesSquare, PlayCircle, ShieldCheck, Upload, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import { api, type User } from "@/lib/api";
import { cx, Spinner } from "./ui";

const UserCtx = createContext<{ user: User; refresh: () => Promise<unknown> } | null>(null);
export const useUser = () => useContext(UserCtx)!;

type NavItem = { href: string; label: string; icon: typeof BookOpen; soon?: boolean };

const STUDENT_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/library", label: "Practice dialogues", icon: BookOpen },
  { href: "/mock-tests", label: "Mock tests", icon: ClipboardCheck },
  { href: "/history", label: "My attempts", icon: History },
  { href: "/videos", label: "Video lessons", icon: PlayCircle, soon: true },
  { href: "/sessions", label: "Live coaching", icon: CalendarDays, soon: true },
  { href: "/questions", label: "Vocabulary drills", icon: GraduationCap, soon: true },
  { href: "/community", label: "Community", icon: MessagesSquare, soon: true },
];

const ASSESSOR_NAV: NavItem[] = [
  { href: "/admin", label: "Submissions", icon: ClipboardCheck },
  { href: "/admin/content", label: "Content studio", icon: Upload },
  { href: "/admin/protection", label: "Content protection", icon: ShieldCheck },
  { href: "/admin/reports", label: "Issue reports", icon: Flag },
  { href: "/library", label: "Dialogue library", icon: FileAudio },
];

export function Logo({ light }: { light?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">B</div>
      <div className="leading-tight">
        <div className={cx("text-sm font-semibold", light ? "text-white" : "text-ink")}>Benchmark</div>
        <div className={cx("text-[11px] font-medium tracking-wide", light ? "text-brand-200" : "text-brand-600")}>NAATI CCL PREP</div>
      </div>
    </div>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  const load = () => api<User>("/me").then(setUser).catch(() => router.replace("/login"));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!user) return <Spinner />;
  const nav = user.role === "assessor" ? ASSESSOR_NAV : STUDENT_NAV;

  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  };

  const sidebar = (
    <nav className="flex h-full flex-col bg-brand-950 px-3 py-5">
      <div className="px-2 pb-6"><Logo light /></div>
      <div className="flex-1 space-y-0.5">
        {nav.map((item) => {
          const active = pathname === item.href || (item.href !== "/admin" && pathname.startsWith(item.href + "/"));
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} onClick={() => setOpen(false)}
              className={cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active ? "bg-white/10 font-medium text-white" : "text-brand-100/80 hover:bg-white/5 hover:text-white",
                item.soon && "opacity-60")}>
              <Icon className="size-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
              {item.soon && <span className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-brand-100">Soon</span>}
            </Link>
          );
        })}
      </div>
      <div className="border-t border-white/10 px-2 pt-4">
        <div className="truncate text-sm font-medium text-white">{user.name}</div>
        <div className="truncate text-xs text-brand-200/70">{user.email}</div>
        <button onClick={logout} className="mt-3 flex items-center gap-2 text-xs text-brand-200 hover:text-white">
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
