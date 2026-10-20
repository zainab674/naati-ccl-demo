"use client";

import { CheckCircle2, ImageUp, Mail, Palette, RotateCcw, Send, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Badge, Button, Card, cx, ErrorNote, Field, inputClass, PageHeader, Spinner, SuccessNote } from "@/components/ui";
import { api } from "@/lib/api";

type ThemeData = { brand_color: string; name: string; tagline: string; logo_url: string | null; palette: Record<string, string>;
  defaults: { brand_color: string; name: string; tagline: string }; contrast: number; min_contrast: number };
type EmailData = { provider: string; email_from: string; reply_to: string; smtp_host: string; smtp_port: number; smtp_user: string;
  smtp_security: string; smtp_password_set: boolean; resend_api_key_set: boolean; source: "settings" | "env"; problem: string };
type Msg = { ok: boolean; text: string } | null;

const PRESETS = [
  { name: "Teal", color: "#1f6778" }, { name: "Blue", color: "#1d4ed8" }, { name: "Indigo", color: "#4338ca" },
  { name: "Purple", color: "#6d28d9" }, { name: "Green", color: "#15803d" }, { name: "Red", color: "#b91c1c" },
  { name: "Orange", color: "#c2410c" }, { name: "Slate", color: "#334155" },
];

// Same mix as the server (services/platform.py) so the preview matches what is saved.
const MIX: [string, number][] = [["50", 0.93], ["100", 0.85], ["200", 0.7], ["300", 0.5], ["400", 0.28], ["500", 0.12], ["600", 0],
  ["700", -0.15], ["800", -0.3], ["900", -0.42], ["950", -0.62]];
function previewPalette(hex: string): Record<string, string> {
  const rgb = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return Object.fromEntries(MIX.map(([k, m]) => {
    const t = m > 0 ? 255 : 0;
    return [k, "#" + rgb.map((c) => Math.round(c + (t - c) * Math.abs(m)).toString(16).padStart(2, "0")).join("")];
  }));
}
function contrastWithWhite(hex: string) {
  const lum = [1, 3, 5].map((i) => { const c = parseInt(hex.slice(i, i + 2), 16) / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 1.05 / (0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2] + 0.05);
}
const validHex = (s: string) => /^#[0-9a-fA-F]{6}$/.test(s);

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null;
  return msg.ok ? <SuccessNote>{msg.text}</SuccessNote> : <ErrorNote>{msg.text}</ErrorNote>;
}

export default function SettingsPage() {
  const [tab, setTab] = useState<"theme" | "email">("theme");
  return (
    <>
      <PageHeader title="Settings" subtitle="Your platform's look and how it sends email." />
      <div className="mb-6 flex gap-2">
        {([["theme", "Theme", Palette], ["email", "Email (SMTP)", Mail]] as const).map(([id, label, Icon]) => (
          <button key={id} onClick={() => setTab(id)}
            className={cx("inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium", tab === id ? "bg-brand-600 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50")}>
            <Icon className="size-4" /> {label}</button>
        ))}
      </div>
      {tab === "theme" ? <ThemeTab /> : <EmailTab />}
    </>
  );
}

// ------------------------------------------------------------------ theme

function ThemeTab() {
  const [t, setT] = useState<ThemeData | null>(null);
  const [color, setColor] = useState("#1f6778");
  const [name, setName] = useState("");
  const [tagline, setTagline] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<Msg>(null);

  const apply = (d: ThemeData) => { setT(d); setColor(d.brand_color); setName(d.name); setTagline(d.tagline); };
  useEffect(() => { api<ThemeData>("/admin/settings/theme").then(apply).catch((e) => setMsg({ ok: false, text: e.message })); }, []);

  const run = async (key: string, fn: () => Promise<ThemeData>, done: string) => {
    setBusy(key);
    setMsg(null);
    try {
      apply(await fn());
      setMsg({ ok: true, text: done });
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
    setBusy("");
  };

  if (!t) return msg ? <Note msg={msg} /> : <Spinner />;
  const ok = validHex(color);
  const ratio = ok ? contrastWithWhite(color) : 0;
  const tooLight = ok && ratio < t.min_contrast;
  const pal = ok ? (color.toLowerCase() === t.defaults.brand_color ? t.palette : previewPalette(color.toLowerCase())) : t.palette;
  const dirty = color.toLowerCase() !== t.brand_color || name !== t.name || tagline !== t.tagline;

  const upload = (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    run("logo", () => api<ThemeData>("/admin/settings/theme/logo", { method: "POST", body: fd }), "Logo uploaded. Reload the page to see it everywhere.");
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
      <Card className="space-y-5 p-6">
        <div>
          <h2 className="font-semibold">Brand colour</h2>
          <p className="text-sm text-slate-500">Used for buttons, links, the sidebar and emails.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button key={p.color} title={p.name} onClick={() => setColor(p.color)}
                className={cx("size-9 rounded-full ring-2 ring-offset-2", color.toLowerCase() === p.color ? "ring-ink" : "ring-transparent")} style={{ background: p.color }}>
                <span className="sr-only">{p.name}</span></button>
            ))}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <input type="color" value={ok ? color : "#1f6778"} onChange={(e) => setColor(e.target.value)} className="h-10 w-14 cursor-pointer rounded border border-slate-200 bg-white p-1" aria-label="Pick a colour" />
            <input value={color} onChange={(e) => setColor(e.target.value.trim())} className={cx(inputClass, "mt-0 !w-32 font-mono")} aria-label="Colour code" />
            {ok && <span className={cx("text-xs", tooLight ? "text-rose-600" : "text-slate-500")}>Contrast with white text {ratio.toFixed(1)}:1{tooLight ? ` (needs ${t.min_contrast}:1, choose a darker shade)` : ""}</span>}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Platform name" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
          <Field label="Tagline (under the name)" value={tagline} maxLength={60} onChange={(e) => setTagline(e.target.value)} />
        </div>
        <div>
          <h2 className="font-semibold">Logo</h2>
          <p className="text-sm text-slate-500">Square PNG, JPG or WebP, up to 512 KB. Without a logo, the first letter of the name is shown.</p>
          <div className="mt-3 flex items-center gap-3">
            {t.logo_url
              // eslint-disable-next-line @next/next/no-img-element -- admin-uploaded logo served by the API
              ? <img src={t.logo_url} alt="Current logo" className="size-12 rounded-lg object-contain ring-1 ring-slate-200" />
              : <div className="flex size-12 items-center justify-center rounded-lg text-lg font-bold text-white" style={{ background: pal["600"] }}>{name.trim().charAt(0).toUpperCase() || "B"}</div>}
            <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg bg-white px-3 text-sm font-medium ring-1 ring-slate-200 hover:bg-slate-50">
              <ImageUp className="size-4" /> {busy === "logo" ? "Uploading..." : t.logo_url ? "Replace logo" : "Upload logo"}
              <input type="file" className="hidden" accept="image/png,image/jpeg,image/webp" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
            </label>
            {t.logo_url && <Button size="sm" variant="ghost" loading={busy === "rmlogo"}
              onClick={() => run("rmlogo", () => api<ThemeData>("/admin/settings/theme/logo", { method: "DELETE" }), "Logo removed.")}><Trash2 className="size-4" /> Remove</Button>}
          </div>
        </div>
        <Note msg={msg} />
        <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4">
          <Button variant="ghost" loading={busy === "reset"} onClick={() => { if (confirm("Reset colour, name and tagline to the defaults?")) run("reset", () => api<ThemeData>("/admin/settings/theme/reset", { method: "POST" }), "Theme reset. Reload the page to see it everywhere."); }}>
            <RotateCcw className="size-4" /> Reset to default</Button>
          <Button disabled={!ok || tooLight || !name.trim() || !dirty} loading={busy === "save"}
            onClick={() => run("save", () => api<ThemeData>("/admin/settings/theme", { method: "PUT", json: { brand_color: color.toLowerCase(), name: name.trim(), tagline: tagline.trim() } }), "Theme saved. Reload the page to see it everywhere.")}>Save theme</Button>
        </div>
        {msg?.ok && <button onClick={() => window.location.reload()} className="text-sm font-medium text-brand-600 hover:underline">Reload now</button>}
      </Card>

      <Card className="overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Preview</div>
        <div className="flex">
          <div className="w-40 shrink-0 space-y-2 p-4" style={{ background: pal["950"] }}>
            <div className="flex items-center gap-2">
              <div className="flex size-7 items-center justify-center rounded-md text-xs font-bold text-white" style={{ background: pal["600"] }}>{name.trim().charAt(0).toUpperCase() || "B"}</div>
              <div className="min-w-0 leading-tight"><div className="truncate text-xs font-semibold text-white">{name || "Name"}</div><div className="truncate text-[10px]" style={{ color: pal["200"] }}>{tagline}</div></div>
            </div>
            <div className="rounded-md px-2 py-1.5 text-xs font-medium text-white" style={{ background: "rgba(255,255,255,0.1)" }}>Dashboard</div>
            <div className="px-2 py-1.5 text-xs" style={{ color: pal["100"] }}>Practice dialogues</div>
            <div className="px-2 py-1.5 text-xs" style={{ color: pal["100"] }}>Mock tests</div>
          </div>
          <div className="flex-1 space-y-4 p-5">
            <div className="text-lg font-semibold">Practice dialogues</div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex h-9 items-center rounded-lg px-4 text-sm font-medium text-white" style={{ background: pal["600"] }}>Start</span>
              <span className="inline-flex h-9 items-center rounded-lg bg-white px-4 text-sm font-medium ring-1 ring-slate-200">Secondary</span>
              <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: pal["50"], color: pal["700"] }}>Free</span>
            </div>
            <p className="text-sm text-slate-600">A <span className="font-medium underline" style={{ color: pal["600"] }}>link</span> in some text.</p>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full w-2/3" style={{ background: pal["500"] }} /></div>
            <div className="flex gap-0.5">{MIX.map(([k]) => <div key={k} title={k} className="h-5 flex-1 first:rounded-l last:rounded-r" style={{ background: pal[k] }} />)}</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ email

function EmailTab() {
  const { user } = useUser();
  const [d, setD] = useState<EmailData | null>(null);
  const [f, setF] = useState<EmailData | null>(null);
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [clear, setClear] = useState({ smtp_password: false, resend_api_key: false });
  const [testTo, setTestTo] = useState(user.email);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  const [testMsg, setTestMsg] = useState<Msg>(null);

  const apply = (x: EmailData) => { setD(x); setF(x); setPassword(""); setApiKey(""); setClear({ smtp_password: false, resend_api_key: false }); };
  useEffect(() => { api<EmailData>("/admin/settings/email").then(apply).catch((e) => setMsg({ ok: false, text: e.message })); }, []);
  if (!d || !f) return msg ? <Note msg={msg} /> : <Spinner />;
  const set = (patch: Partial<EmailData>) => setF({ ...f, ...patch });

  const save = async () => {
    setBusy("save");
    setMsg(null);
    try {
      apply(await api<EmailData>("/admin/settings/email", { method: "PUT", json: {
        provider: f.provider, email_from: f.email_from, reply_to: f.reply_to, smtp_host: f.smtp_host, smtp_port: Number(f.smtp_port),
        smtp_user: f.smtp_user, smtp_security: f.smtp_security,
        smtp_password: clear.smtp_password ? "" : password || null, resend_api_key: clear.resend_api_key ? "" : apiKey || null,
      } }));
      setMsg({ ok: true, text: "Email settings saved. Send a test email to check them." });
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
    setBusy("");
  };

  const test = async () => {
    setBusy("test");
    setTestMsg(null);
    try {
      const r = await api<{ ok: boolean; provider: string; error: string }>("/admin/settings/email/test", { method: "POST", json: { to: testTo } });
      setTestMsg(r.ok ? { ok: true, text: r.provider === "console" ? "Sent to the server log (development mode: no real email is sent)." : `Test email sent to ${testTo} via ${r.provider.toUpperCase()}. Check the inbox (and spam).` }
        : { ok: false, text: `Sending failed: ${r.error || "unknown error"}` });
    } catch (e) { setTestMsg({ ok: false, text: (e as Error).message }); }
    setBusy("");
  };

  const reset = async () => {
    if (!confirm("Forget these settings and use the server's .env email settings?")) return;
    setBusy("reset");
    try { apply(await api<EmailData>("/admin/settings/email/reset", { method: "POST" })); setMsg({ ok: true, text: "Now using the server's .env settings." }); }
    catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
    setBusy("");
  };

  const dirty = JSON.stringify(f) !== JSON.stringify(d) || !!password || !!apiKey || clear.smtp_password || clear.resend_api_key;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <Card className="space-y-5 p-6">
        <div className="flex items-start justify-between gap-3">
          <div><h2 className="font-semibold">Sending email</h2>
            <p className="text-sm text-slate-500">Welcome, password reset, invites, receipts and results emails.</p></div>
          <Badge tone={d.source === "settings" ? "brand" : "slate"}>{d.source === "settings" ? "Saved here" : "Using server .env"}</Badge>
        </div>
        {d.problem && <ErrorNote>{d.problem}</ErrorNote>}
        <fieldset className="grid gap-2 sm:grid-cols-3">
          {[["smtp", "SMTP server", "Gmail, Microsoft 365, your host's mail server"], ["resend", "Resend", "Resend.com API key"], ["console", "Development", "Not sent; shown in the server log"]].map(([id, label, hint]) => (
            <label key={id} className={cx("cursor-pointer rounded-lg p-3 ring-1", f.provider === id ? "bg-brand-50 ring-brand-600" : "ring-slate-200 hover:bg-slate-50")}>
              <input type="radio" className="sr-only" checked={f.provider === id} onChange={() => set({ provider: id })} />
              <div className="text-sm font-medium">{label}</div><div className="text-xs text-slate-500">{hint}</div>
            </label>
          ))}
        </fieldset>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="From" value={f.email_from} onChange={(e) => set({ email_from: e.target.value })} hint={'e.g. "Benchmark Education <no-reply@yourdomain.com>"'} />
          <Field label="Reply-to (optional)" value={f.reply_to} onChange={(e) => set({ reply_to: e.target.value })} hint="Where student replies go." />
        </div>
        {f.provider === "smtp" && (
          <div className="space-y-3 rounded-lg bg-slate-50 p-4">
            <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
              <Field label="SMTP server (host)" value={f.smtp_host} placeholder="smtp.gmail.com" onChange={(e) => set({ smtp_host: e.target.value })} />
              <Field label="Port" type="number" value={f.smtp_port} onChange={(e) => set({ smtp_port: Number(e.target.value) })} />
            </div>
            <label className="block"><span className="text-sm font-medium text-slate-700">Security</span>
              <select className={inputClass} value={f.smtp_security} onChange={(e) => {
                const sec = e.target.value;
                set({ smtp_security: sec, smtp_port: sec === "ssl" ? 465 : f.smtp_port === 465 ? 587 : f.smtp_port });
              }}>
                <option value="starttls">STARTTLS (usually port 587)</option><option value="ssl">SSL/TLS (usually port 465)</option><option value="none">None (not recommended)</option>
              </select></label>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Username" value={f.smtp_user} autoComplete="off" onChange={(e) => set({ smtp_user: e.target.value })} />
              <Field label="Password" type="password" autoComplete="new-password" value={password} disabled={clear.smtp_password}
                placeholder={d.smtp_password_set ? "Saved (leave empty to keep)" : ""} onChange={(e) => setPassword(e.target.value)}
                hint={d.smtp_password_set ? <button type="button" className="text-rose-600 hover:underline" onClick={() => setClear({ ...clear, smtp_password: !clear.smtp_password })}>{clear.smtp_password ? "Keep the saved password" : "Remove the saved password"}</button> : "For Gmail, use an app password."} />
            </div>
          </div>
        )}
        {f.provider === "resend" && (
          <div className="rounded-lg bg-slate-50 p-4">
            <Field label="Resend API key" type="password" autoComplete="off" value={apiKey} disabled={clear.resend_api_key}
              placeholder={d.resend_api_key_set ? "Saved (leave empty to keep)" : "re_..."} onChange={(e) => setApiKey(e.target.value)}
              hint={d.resend_api_key_set ? <button type="button" className="text-rose-600 hover:underline" onClick={() => setClear({ ...clear, resend_api_key: !clear.resend_api_key })}>{clear.resend_api_key ? "Keep the saved key" : "Remove the saved key"}</button> : "The From address must use a domain verified in Resend."} />
          </div>
        )}
        <Note msg={msg} />
        <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4">
          {d.source === "settings" ? <Button variant="ghost" loading={busy === "reset"} onClick={reset}><RotateCcw className="size-4" /> Use server .env settings</Button> : <span />}
          <Button onClick={save} loading={busy === "save"} disabled={!dirty}>Save email settings</Button>
        </div>
      </Card>

      <div className="space-y-6">
        <Card className="space-y-3 p-6">
          <h2 className="font-semibold">Send a test email</h2>
          <p className="text-sm text-slate-500">Uses the saved settings. Save first if you changed anything.</p>
          <Field label="Send to" type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
          <Note msg={testMsg} />
          <Button variant="secondary" loading={busy === "test"} disabled={dirty || !testTo} onClick={test}><Send className="size-4" /> Send test email</Button>
          {dirty && <p className="text-xs text-amber-700">You have unsaved changes.</p>}
        </Card>
        <Card className="space-y-2 p-6 text-sm text-slate-600">
          <h2 className="font-semibold text-ink">Common settings</h2>
          <p><b>Gmail / Google Workspace:</b> smtp.gmail.com, port 587, STARTTLS, your address and an <i>app password</i>.</p>
          <p><b>Microsoft 365:</b> smtp.office365.com, port 587, STARTTLS.</p>
          <p><b>Port 465:</b> choose SSL/TLS.</p>
          <p className="flex items-center gap-1.5 pt-1 text-xs text-slate-500"><CheckCircle2 className="size-3.5" /> Passwords and keys are stored encrypted and are never shown again.</p>
        </Card>
      </div>
    </div>
  );
}
