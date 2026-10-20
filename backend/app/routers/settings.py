"""Platform settings: theme (public read, admin edit) and email delivery (admin only, secrets write-only)."""
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_admin
from ..services import platform, ratelimit
from ..services.email import send_template
from ..services.storage import get_storage

public = APIRouter(prefix="/api/public", tags=["public"])
admin = APIRouter(prefix="/api/admin/settings", tags=["admin"], dependencies=[Depends(require_admin)])

LOGO_TYPES = {"image/png": ("png", b"\x89PNG"), "image/jpeg": ("jpg", b"\xff\xd8"), "image/webp": ("webp", b"RIFF")}
LOGO_MAX_BYTES = 512 * 1024
PLAIN_TEXT = re.compile(r"^[^<>]*$")  # names appear in emails and pages; no markup


def theme_dict(t: dict) -> dict:
    return {"brand_color": t["brand_color"], "name": t["name"], "tagline": t["tagline"],
            "palette": {str(k): v for k, v in t["palette"].items()},
            "logo_url": f"/api/public/theme/logo?v={t['logo_key'].rsplit('/', 1)[-1].split('.')[0]}" if t["logo_key"] else None}


# ------------------------------------------------------------------ theme

@public.get("/theme")
def get_theme(db: Session = Depends(get_db)):
    return theme_dict(platform.theme(db))


@public.get("/theme/logo")
def theme_logo(db: Session = Depends(get_db)):
    key = platform.theme(db)["logo_key"]
    data = get_storage().get(key) if key else None
    if data is None:
        raise HTTPException(404, "No logo")
    ext = key.rsplit(".", 1)[-1]
    ctype = next(t for t, (e, _) in LOGO_TYPES.items() if e == ext)
    # The URL carries a version (?v=), so the image can be cached; a new upload gets a new URL.
    return Response(data, media_type=ctype, headers={"Cache-Control": "public, max-age=31536000, immutable",
                                                     "X-Content-Type-Options": "nosniff"})


class ThemeIn(BaseModel):
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    name: str | None = Field(default=None, min_length=1, max_length=60)
    tagline: str | None = Field(default=None, max_length=60)


@admin.get("/theme")
def admin_theme(db: Session = Depends(get_db)):
    t = platform.theme(db)
    return {**theme_dict(t), "defaults": platform.DEFAULT_THEME,
            "contrast": platform.contrast_with_white(t["brand_color"]), "min_contrast": platform.MIN_CONTRAST}


@admin.put("/theme")
def save_theme(body: ThemeIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    value = platform.get_value(db, "theme")
    for field in ("name", "tagline"):
        v = getattr(body, field)
        if v is not None and not PLAIN_TEXT.match(v):
            raise HTTPException(400, f"The {field} cannot contain < or >")
    if body.brand_color:
        ratio = platform.contrast_with_white(body.brand_color)
        if ratio < platform.MIN_CONTRAST:
            raise HTTPException(400, f"This colour is too light for white text on buttons (contrast {ratio}:1, needs "
                                     f"{platform.MIN_CONTRAST}:1). Choose a darker shade.")
        value["brand_color"] = body.brand_color.lower()
    for field in ("name", "tagline"):
        if field in body.model_fields_set and getattr(body, field) is not None:
            value[field] = getattr(body, field).strip()
    platform.set_value(db, "theme", value, cu.id)
    db.commit()
    return admin_theme(db)


@admin.post("/theme/reset")
def reset_theme(cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Back to the default colour, name and tagline (an uploaded logo is kept)."""
    logo = platform.get_value(db, "theme").get("logo_key")
    platform.set_value(db, "theme", {"logo_key": logo} if logo else {}, cu.id)
    db.commit()
    return admin_theme(db)


@admin.post("/theme/logo")
async def upload_logo(file: UploadFile = File(...), cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    data = await file.read(LOGO_MAX_BYTES + 1)
    if len(data) > LOGO_MAX_BYTES:
        raise HTTPException(413, "The logo must be 512 KB or smaller")
    kind = next(((t, ext) for t, (ext, magic) in LOGO_TYPES.items() if data.startswith(magic)), None)
    if not kind or (kind[1] == "webp" and data[8:12] != b"WEBP"):
        raise HTTPException(400, "Upload a PNG, JPG or WebP image")
    value = platform.get_value(db, "theme")
    old = value.get("logo_key")
    value["logo_key"] = f"branding/logo-{uuid.uuid4().hex[:12]}.{kind[1]}"
    get_storage().put(value["logo_key"], data, kind[0])
    if old:
        get_storage().delete(old)
    platform.set_value(db, "theme", value, cu.id)
    db.commit()
    return admin_theme(db)


@admin.delete("/theme/logo")
def remove_logo(cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    value = platform.get_value(db, "theme")
    if value.get("logo_key"):
        get_storage().delete(value.pop("logo_key"))
    platform.set_value(db, "theme", value, cu.id)
    db.commit()
    return admin_theme(db)


# ------------------------------------------------------------------ email

def email_dict(db: Session) -> dict:
    c = platform.email_config(db)
    return {"provider": c.provider, "email_from": c.email_from, "reply_to": c.reply_to, "smtp_host": c.smtp_host,
            "smtp_port": c.smtp_port, "smtp_user": c.smtp_user, "smtp_security": c.smtp_security,
            # Secrets are write-only: the page only learns whether one is set.
            "smtp_password_set": bool(c.smtp_password), "resend_api_key_set": bool(c.resend_api_key),
            "source": c.source, "problem": c.secret_problem}


class EmailIn(BaseModel):
    provider: str
    email_from: str = Field(min_length=3, max_length=200)
    reply_to: str = Field(default="", max_length=200)
    smtp_host: str = Field(default="", max_length=200)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="", max_length=200)
    smtp_security: str = "starttls"
    # None = keep the saved value; "" = clear it.
    smtp_password: str | None = Field(default=None, max_length=500)
    resend_api_key: str | None = Field(default=None, max_length=500)


@admin.get("/email")
def get_email(db: Session = Depends(get_db)):
    return email_dict(db)


@admin.put("/email")
def save_email(body: EmailIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    if body.provider not in platform.PROVIDERS:
        raise HTTPException(400, f"Provider must be one of {', '.join(platform.PROVIDERS)}")
    if body.smtp_security not in platform.SECURITY:
        raise HTTPException(400, f"Security must be one of {', '.join(platform.SECURITY)}")
    if body.provider == "smtp" and not body.smtp_host.strip():
        raise HTTPException(400, "Enter the SMTP server (host)")
    if any(ch in body.email_from + body.reply_to for ch in "\r\n"):
        raise HTTPException(400, "Addresses cannot contain line breaks")
    old = platform.get_value(db, "email")
    value = {"provider": body.provider, "email_from": body.email_from.strip(), "reply_to": body.reply_to.strip(),
             "smtp_host": body.smtp_host.strip(), "smtp_port": body.smtp_port, "smtp_user": body.smtp_user.strip(),
             "smtp_security": body.smtp_security}
    for field in ("smtp_password", "resend_api_key"):
        new = getattr(body, field)
        if new is None:
            if old.get(field + "_enc"):
                value[field + "_enc"] = old[field + "_enc"]
        elif new:
            value[field + "_enc"] = platform.encrypt(new)
    platform.set_value(db, "email", value, cu.id)
    db.commit()
    return email_dict(db)


@admin.post("/email/reset")
def reset_email(cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Forget the saved settings and use the server's .env values again."""
    platform.set_value(db, "email", {}, cu.id)
    db.commit()
    return email_dict(db)


class TestIn(BaseModel):
    to: EmailStr


@admin.post("/email/test")
def test_email(body: TestIn, cu: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    ratelimit.enforce(f"email-test:{cu.id}", 5)
    entry = send_template(db, "test", str(body.to), {}, user_id=cu.id)
    return {"ok": entry.status.value == "sent", "provider": entry.provider, "error": entry.error}
