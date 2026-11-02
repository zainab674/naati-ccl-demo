"use client";

import {
  BookOpen, ChevronDown, ClipboardCheck, Eye, Flag, GraduationCap, LayoutDashboard, Library, LogOut, Megaphone, Menu, Settings, Shield, Sparkles, Target, Upload, UserCog, Users, UsersRound, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { api, isStaff, type User } from "@/lib/api";
import { JobTicker } from "./JobTicker";
import { Logo } from "./Logo";
import { cx, Spinner } from "./ui";

export { Logo };

const UserCtx = createContext<{ user: User; refresh: () => Promise<unknown> } | null>(null);
export const useUser = () => useContext(UserCtx)!;

type NavItem = { href: string; label: string; icon: typeof BookOpen; adminOnly?: boolean };
type NavGroup = { label: string; icon: typeof BookOpen; items: (NavItem | { label: string; icon: typeof BookOpen; soon: true })[] };

// Student menu from the client's Round 1 mockup. My attempts is reached from the dashboard's Recent Attempts.
const STUDENT_NAV: (NavItem | NavGroup)[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { label: "Learning Hub", icon: Library, items: [
    { href: "/courses", label: "Courses", icon: GraduationCap },
    { href: "/resources", label: "Resources", icon: BookOpen },
    { label: "Classes and Coaching", icon: UsersRound, soon: true },
  ] },
  { label: "Practice Hub", icon: Target, items: [
    { href: "/mock-tests", label: "Mock Test", icon: ClipboardCheck },
    { label: "Skill Mastery", icon: Sparkles, soon: true },
  ] },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/students", label: "Students", icon: Users },
  { href: "/admin/review", label: "Review queue", icon: Flag },
  { href: "/admin/dialogues", label: "Dialogues", icon: BookOpen, adminOnly: true },
  { href: "/admin/mock-tests", label: "Mock tests", icon: ClipboardCheck, adminOnly: true },
  { href: "/admin/courses", label: "Courses", icon: GraduationCap },
  { href: "/admin/resources", label: "Resources", icon: Library, adminOnly: true },
  { href: "/admin/announcements", label: "Announcements", icon: Megaphone, adminOnly: true },
  { href: "/admin/imports", label: "CSV import", icon: Upload, adminOnly: true },
  { href: "/admin/team", label: "Team", icon: UserCog, adminOnly: true },
  { href: "/admin/settings", label: "Settings", icon: Settings, adminOnly: true },
];

// Pages under /admin a teacher may open (the API enforces the same split).
const TEACHER_PATHS = ["/admin", "/admin/students", "/admin/review", "/admin/attempts", "/admin/courses"];
const teacherMayOpen = (path: string) =>
  TEACHER_PATHS.some((p) => path === p || (p !== "/admin" && path.startsWith(p + "/")));

export default function AppShell({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);
  const [foldedGroups, setFoldedGroups] = useState<Set<string>>(new Set());
  const pathname = usePathname();
  const router = useRouter();

  const load = useCallback(() => api<User>("/me").then((u) => {
    if (admin && !isStaff(u)) { router.replace("/dashboard"); return; }
    setUser(u);
  }), [admin, router]);
  const blocked = !!(admin && user?.role === "teacher" && !teacherMayOpen(pathname));
  useEffect(() => { if (blocked) router.replace("/admin"); }, [blocked, router]);
  useEffect(() => { load().catch(() => {}); }, [load]);

  if (!user || blocked) return <Spinner />;
  const nav: (NavItem | NavGroup)[] = admin ? ADMIN_NAV.filter((item) => user.role === "admin" || !item.adminOnly) : STUDENT_NAV;
  const isActive = (href: string) => pathname === href || (href !== "/admin" && pathname.startsWith(href + "/"));
  const toggleGroup = (label: string) => setFoldedGroups((s) => {
    const n = new Set(s);
    if (n.has(label)) n.delete(label); else n.add(label);
    return n;
  });
  const navLink = (item: NavItem, sub = false) => {
    const Icon = item.icon;
    return (
      <Link key={item.href} href={item.href} onClick={() => setOpen(false)} aria-current={isActive(item.href) ? "page" : undefined}
        className={cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors", sub && "pl-9",
          isActive(item.href) ? "bg-white/10 font-medium text-white" : "text-brand-100/80 hover:bg-white/5 hover:text-white")}>
        <Icon className="size-4 shrink-0" />
        <span className="flex-1">{item.label}</span>
      </Link>
    );
  };

  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  };

  const sidebar = (
    <nav className="flex h-full flex-col bg-brand-950 px-3 py-5">
      <div className="px-2 pb-6"><Link href="/"><Logo light /></Link></div>
      <div className="flex-1 space-y-0.5">
        {nav.map((item) => {
          if ("href" in item) return navLink(item);
          const GroupIcon = item.icon;
          const folded = foldedGroups.has(item.label);
          return (
            <div key={item.label} className="pt-1">
              <button onClick={() => toggleGroup(item.label)} aria-expanded={!folded}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-semibold text-white hover:bg-white/5">
                <GroupIcon className="size-4 shrink-0" />
                <span className="flex-1">{item.label}</span>
                <ChevronDown className={cx("size-4 shrink-0 text-brand-200 transition-transform", folded && "-rotate-90")} />
              </button>
              {!folded && <div className="mt-0.5 space-y-0.5">
                {item.items.map((sub) => {
                  if ("href" in sub) return navLink(sub, true);
                  const SubIcon = sub.icon;
                  return (
                    <div key={sub.label} className="flex items-center gap-3 rounded-lg px-3 py-2 pl-9 text-sm text-brand-100/50">
                      <SubIcon className="size-4 shrink-0" />
                      <span className="flex-1">{sub.label}</span>
                      <span className="rounded-full border border-white/20 px-1.5 py-0.5 text-[10px] leading-none text-brand-100/70">Soon</span>
                    </div>
                  );
                })}
              </div>}
            </div>
          );
        })}
      </div>
      <div className="space-y-0.5 border-t border-white/10 pt-3">
        <Link href="/account" onClick={() => setOpen(false)} className={cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
          isActive("/account") ? "bg-white/10 font-medium text-white" : "text-brand-100/80 hover:bg-white/5 hover:text-white")}>
          <Settings className="size-4 shrink-0" /> Account and Billing
        </Link>
        <button onClick={logout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-brand-100/80 hover:bg-white/5 hover:text-white">
          <LogOut className="size-4 shrink-0" /> Sign Out
        </button>
      </div>
    </nav>
  );

  return (
    <UserCtx.Provider value={{ user, refresh: load }}>
      <JobTicker />
      <div className="flex min-h-screen">
        <aside className="fixed inset-y-0 left-0 hidden w-60 lg:block">{sidebar}</aside>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
            <aside className="absolute inset-y-0 left-0 w-64">{sidebar}</aside>
          </div>
        )}
        <div className="min-w-0 flex-1 lg:pl-60">
          {/* Top bar: menu on phones; for admins, the switch between the admin area and the student view (top right). */}
          <header className={cx("sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-8",
            !isStaff(user) && "lg:hidden")}>
            <button onClick={() => setOpen(!open)} aria-label="Menu" className="rounded p-1.5 hover:bg-slate-100 lg:hidden">
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
            <div className="lg:hidden"><Logo /></div>
            {isStaff(user) && (
              <Link href={admin ? "/dashboard" : "/admin"}
                className="ml-auto inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-medium text-ink shadow-sm ring-1 ring-slate-200 hover:bg-slate-50">
                {admin ? <><Eye className="size-4" /> Student view</> : <><Shield className="size-4" /> {user.role === "admin" ? "Admin" : "Teacher"}</>}
              </Link>
            )}
          </header>
          <main className="mx-auto max-w-[1500px] px-4 py-8 sm:px-8">{children}</main>
        </div>
      </div>
    </UserCtx.Provider>
  );
}
