export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type FieldError = { loc?: (string | number)[]; msg?: string };

function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: "email: value is not a valid email address"
    return detail.map((d: FieldError) => {
      const field = d.loc?.filter((p) => p !== "body").join(".");
      return field ? `${field}: ${d.msg}` : d.msg;
    }).join("; ");
  }
  return fallback;
}

/** Same-origin call to the FastAPI backend (Next rewrites /api/* to it), so the httpOnly session cookie is sent. */
export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown; noAuthRedirect?: boolean } = {}): Promise<T> {
  const { json, headers, noAuthRedirect, ...rest } = init;
  const res = await fetch(`/api${path}`, {
    credentials: "same-origin",
    cache: "no-store",
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json", ...headers } : headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = errorMessage(data.detail, msg);
    } catch {}
    if (res.status === 401 && !noAuthRedirect && typeof window !== "undefined" && !path.startsWith("/auth") && !path.startsWith("/public")) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      // Outside React (plain fetch helper), so no router is available here.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `${window.location.origin}/login?next=${next}`;
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

// ---------- types

export type User = {
  id: string; email: string; first_name: string; last_name: string; name: string; role: "student" | "admin";
  subscription_status: "Active" | "Trial" | "Expired" | "Inactive"; has_active_plan: boolean;
  target_exam_date: string | null;
};

// ---------- formatting

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString("en-AU", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** Only allow same-site relative redirects after login (no open redirect). */
export function safeNext(next: string | null, fallback: string) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}
