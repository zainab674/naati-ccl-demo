"""Transactional email templates: (subject, html, text). Context values are HTML-escaped.

The platform name and brand colour come from the admin theme (render() sets them for the current message)."""
from contextvars import ContextVar
from html import escape

_brand: ContextVar[tuple[str, str]] = ContextVar("brand", default=("Benchmark Education", "#1f6778"))


class _Brand(str):
    """BRAND reads the current platform name, so templates keep writing f"...{BRAND}..."."""
    def __format__(self, spec):
        return format(_brand.get()[0], spec)

    def __str__(self):
        return _brand.get()[0]

    def upper(self):
        return _brand.get()[0].upper()


BRAND = _Brand("")


def _layout(title: str, body_html: str, cta: tuple[str, str] | None = None) -> str:
    button = ""
    if cta:
        label, url = cta
        button = (f'<p style="margin:28px 0"><a href="{escape(url)}" style="background:{escape(_brand.get()[1])};color:#ffffff;'
                  f'padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block">'
                  f'{escape(label)}</a></p>')
    return f"""<!doctype html>
<html><body style="margin:0;background:#f6f8f9;font-family:Arial,Helvetica,sans-serif;color:#0f1c22">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px;padding:32px">
<tr><td>
<div style="font-weight:700;color:{escape(_brand.get()[1])};font-size:14px;letter-spacing:.04em">{BRAND.upper()} · NAATI CCL</div>
<h1 style="font-size:22px;margin:16px 0 12px">{escape(title)}</h1>
<div style="font-size:15px;line-height:1.6">{body_html}</div>
{button}
<p style="font-size:12px;color:#64748b;margin-top:32px">You are receiving this email because you have an account with {BRAND}.</p>
</td></tr></table>
</td></tr></table>
</body></html>"""


def _welcome(c: dict) -> tuple[str, str, str]:
    subject = f"Welcome to {BRAND}"
    html = _layout(f"Welcome, {c.get('first_name', '')}", (
        "<p>Your account is ready. Start with the free introduction course and the free practice dialogue, "
        "then choose a plan when you are ready for full mock tests.</p>"), ("Go to your dashboard", c["dashboard_url"]))
    text = (f"Welcome, {c.get('first_name', '')}\n\nYour account is ready. Start with the free introduction course "
            f"and the free practice dialogue.\n\nDashboard: {c['dashboard_url']}\n")
    return subject, html, text


def _password_reset(c: dict) -> tuple[str, str, str]:
    mins = int(c.get("expires_minutes", 60))
    subject = "Reset your password"
    html = _layout("Reset your password", (
        f"<p>Hi {escape(c.get('first_name', ''))},</p><p>We received a request to reset your password. "
        f"This link works once and expires in {mins} minutes.</p>"
        "<p>If you did not ask for this, you can ignore this email; your password will not change.</p>"),
        ("Choose a new password", c["reset_url"]))
    text = (f"Hi {c.get('first_name', '')},\n\nReset your password (link expires in {mins} minutes):\n"
            f"{c['reset_url']}\n\nIf you did not ask for this, ignore this email.\n")
    return subject, html, text


def _enrolment_invite(c: dict) -> tuple[str, str, str]:
    hours = int(c.get("expires_hours", 72))
    subject = f"Your {BRAND} CCL practice account"
    html = _layout(f"Welcome, {c.get('first_name', '')}", (
        f"<p>Your teacher at {BRAND} has created a NAATI CCL practice account for you.</p>"
        f"<p>Choose a password to sign in. This link works once and expires in {hours} hours; after that, use "
        "\"Forgot password\" on the sign-in page.</p>"), ("Set your password", c["invite_url"]))
    text = (f"Welcome, {c.get('first_name', '')}\n\nYour teacher at {BRAND} has created a NAATI CCL practice account "
            f"for you. Set your password (link expires in {hours} hours):\n{c['invite_url']}\n")
    return subject, html, text


def _receipt(c: dict) -> tuple[str, str, str]:
    subject = f"Payment receipt: {c.get('plan_name', 'your plan')}"
    rows = [("Plan", c.get("plan_name", "")), ("Amount", c.get("amount_display", "")), ("Date", c.get("date", ""))]
    table = "".join(f'<tr><td style="padding:4px 16px 4px 0;color:#64748b">{escape(k)}</td>'
                    f'<td style="padding:4px 0"><b>{escape(str(v))}</b></td></tr>' for k, v in rows if v)
    cta = ("View receipt", c["receipt_url"]) if c.get("receipt_url") else ("Go to your dashboard", c["dashboard_url"])
    html = _layout("Thank you for your payment", (
        f"<p>Hi {escape(c.get('first_name', ''))}, your payment was successful and your access is active.</p>"
        f"<table>{table}</table>"), cta)
    text = (f"Hi {c.get('first_name', '')}, your payment was successful.\n\n"
            + "".join(f"{k}: {v}\n" for k, v in rows if v)
            + (f"\nReceipt: {c['receipt_url']}\n" if c.get("receipt_url") else ""))
    return subject, html, text


def _results_ready(c: dict) -> tuple[str, str, str]:
    subject = f"Your results are ready: {c.get('title', 'mock test')}"
    score = f"{c['total']:g} / {c['max']:g}" if c.get("total") is not None else ""
    html = _layout("Your results are ready", (
        f"<p>Hi {escape(c.get('first_name', ''))}, we have finished scoring <b>{escape(c.get('title', ''))}</b>.</p>"
        + (f"<p style='font-size:18px'>Estimated score: <b>{escape(score)}</b> ({escape(c.get('result', ''))})</p>"
           if score else "")
        + "<p>Open your results to see every deduction, what we heard, and suggested versions.</p>"),
        ("View results", c["results_url"]))
    text = (f"Hi {c.get('first_name', '')}, your results for {c.get('title', '')} are ready.\n"
            + (f"Estimated score: {score} ({c.get('result', '')})\n" if score else "")
            + f"\n{c['results_url']}\n")
    return subject, html, text


TEMPLATES = {
    "welcome": _welcome,
    "password_reset": _password_reset,
    "enrolment_invite": _enrolment_invite,
    "receipt": _receipt,
    "results_ready": _results_ready,
}


def _test(c: dict) -> tuple[str, str, str]:
    subject = f"{BRAND}: test email"
    html = _layout("Test email", (
        "<p>This is a test email from your platform's Settings page. If you can read it, email delivery works.</p>"))
    text = "This is a test email from your platform's Settings page. If you can read it, email delivery works.\n"
    return subject, html, text


TEMPLATES["test"] = _test


def render(name: str, context: dict, brand: str | None = None, color: str | None = None) -> tuple[str, str, str]:
    if name not in TEMPLATES:
        raise KeyError(f"Unknown email template {name}")
    token = _brand.set((brand or "Benchmark Education", color or "#1f6778"))
    try:
        return TEMPLATES[name](context)
    finally:
        _brand.reset(token)
