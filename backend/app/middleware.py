"""HTTP hardening: Origin check on state-changing requests (CSRF defence in depth) and security headers.

Session cookies are httpOnly + SameSite=Lax (+ Secure in production), so browsers do not send them on cross-site
POSTs anyway; the Origin check also blocks a cross-site request that somehow carries them.
"""
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .settings import get_settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT = ("/api/stripe/webhook",)  # server-to-server, verified by Stripe's signature


def allowed_origins() -> set[str]:
    s = get_settings()
    origins = {s.app_url.rstrip("/")}
    origins |= {o.strip().rstrip("/") for o in s.cors_origins.split(",") if o.strip()}
    if not s.is_production:
        origins |= {"http://localhost:3000", "http://127.0.0.1:3000"}
    return origins


def _origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE and request.url.path.startswith("/api/") and not request.url.path.startswith(CSRF_EXEMPT):
            origin = request.headers.get("origin") or _origin_of(request.headers.get("referer", ""))
            # Same-host requests (through the Next.js proxy or Caddy) are fine; so are non-browser clients (no Origin).
            host_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if origin and origin != host_origin and origin not in allowed_origins():
                return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response
