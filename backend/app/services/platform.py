"""Admin-editable platform settings: the theme (brand colour, name, tagline, logo) and email delivery (SMTP/Resend).

Stored as PlatformSetting rows. Email secrets (SMTP password, Resend API key) are encrypted with a key derived from
SECRET_KEY and are never returned to the browser. When no email settings have been saved, the .env values apply.
"""
import base64
import hashlib
import re
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PlatformSetting
from ..settings import get_settings

# ------------------------------------------------------------------ storage

def get_value(db: Session, key: str) -> dict:
    row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    return dict(row.value) if row else {}


def set_value(db: Session, key: str, value: dict, user_id=None) -> None:
    row = db.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
    if not row:
        row = PlatformSetting(key=key, value={})
        db.add(row)
    row.value, row.updated_by = value, user_id


def _fernet() -> Fernet:
    digest = hashlib.sha256(("platform-settings:" + get_settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(token: str) -> str | None:
    """None when the value cannot be read (e.g. SECRET_KEY changed since it was saved)."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


# ------------------------------------------------------------------ theme

DEFAULT_THEME = {"brand_color": "#1f6778", "name": "Benchmark Education", "tagline": "NAATI CCL PREP"}
# The hand-tuned default palette (frontend/src/app/globals.css); other colours get a generated palette.
DEFAULT_PALETTE = {50: "#eef7f8", 100: "#d5ecef", 200: "#aed9df", 300: "#7cbfc9", 400: "#479daa", 500: "#2b808f",
                   600: "#1f6778", 700: "#1c5563", 800: "#1c4652", 900: "#1a3b45", 950: "#0c262e"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
# Shade -> how much white (+) or black (-) to mix into the chosen colour, which is used as shade 600.
MIX = {50: 0.93, 100: 0.85, 200: 0.70, 300: 0.50, 400: 0.28, 500: 0.12, 600: 0, 700: -0.15, 800: -0.30, 900: -0.42,
       950: -0.62}
MIN_CONTRAST = 4.5  # white button text on the brand colour must stay readable (WCAG AA)


def _rgb(hex_: str) -> tuple[int, int, int]:
    return int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16)


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def palette(color: str) -> dict[int, str]:
    if color.lower() == DEFAULT_THEME["brand_color"]:
        return dict(DEFAULT_PALETTE)
    base = _rgb(color)
    out = {}
    for shade, m in MIX.items():
        target = 255 if m > 0 else 0
        out[shade] = _hex(tuple(c + (target - c) * abs(m) for c in base))
    return out


def contrast_with_white(color: str) -> float:
    def lum(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lum(c) for c in _rgb(color))
    return round(1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05), 2)


def theme(db: Session) -> dict:
    t = {**DEFAULT_THEME, **{k: v for k, v in get_value(db, "theme").items() if v not in (None, "")}}
    return {"brand_color": t["brand_color"], "name": t["name"], "tagline": t["tagline"],
            "logo_key": t.get("logo_key") or "", "palette": palette(t["brand_color"])}


# ------------------------------------------------------------------ email

PROVIDERS = ("console", "smtp", "resend")
SECURITY = ("starttls", "ssl", "none")


@dataclass
class EmailConfig:
    provider: str
    email_from: str
    reply_to: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_security: str
    resend_api_key: str
    source: str            # "settings" (saved by an admin) or "env"
    secret_problem: str = ""


def email_config(db: Session | None) -> EmailConfig:
    s = get_settings()
    saved = get_value(db, "email") if db is not None else {}
    if not saved.get("provider"):
        return EmailConfig(s.email_provider, s.email_from, s.email_reply_to, s.smtp_host, s.smtp_port, s.smtp_user,
                           s.smtp_password, "starttls" if s.smtp_starttls else "none", s.resend_api_key, "env")
    problem = ""
    secrets = {}
    for field in ("smtp_password", "resend_api_key"):
        token = saved.get(field + "_enc") or ""
        value = decrypt(token) if token else ""
        if value is None:
            value, problem = "", "A saved password or API key could not be decrypted (SECRET_KEY changed). Enter it again."
        secrets[field] = value
    return EmailConfig(saved["provider"], saved.get("email_from") or s.email_from, saved.get("reply_to", ""),
                       saved.get("smtp_host", ""), int(saved.get("smtp_port") or 587), saved.get("smtp_user", ""),
                       secrets["smtp_password"], saved.get("smtp_security", "starttls"), secrets["resend_api_key"],
                       "settings", problem)
