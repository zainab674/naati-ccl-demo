# Security controls

| Area | Control | Where |
|---|---|---|
| Sessions | HS256 JWT in an httpOnly, SameSite=Lax cookie; Secure forced in production; `session_version` signs out every session after a password change/reset | `app/security.py`, `app/deps.py` |
| Passwords | PBKDF2-SHA256 (310k iterations, per-user salt); reset tokens are random, single use, 60 min, stored as SHA-256 hashes; reset requests never reveal whether an email exists | `app/routers/auth.py` |
| CSRF | SameSite cookies + Origin/Referer check on every state-changing `/api` request (Stripe webhook exempt, signature-verified instead) | `app/middleware.py` |
| Rate limits | login (per IP and per email), signup, forgot/reset password, recording uploads, segment plays, protected media, AI suggestions | `app/services/ratelimit.py` (in-memory per process) |
| Authorisation | every `/api/admin/*` route depends on `require_admin` (tested route by route); attempts, recordings and waveforms are owner-or-admin only; paid content (including hub files) returns 402 without an active plan; teacher-granted access expires on its end date; deactivating a student ends their sessions | `app/deps.py`, `tests/test_security.py` |
| Audio protection | AES-128 HLS per segment; signed URLs expire in 5 minutes and are bound to the attempt owner and the login session; AES key fetch limit per play; plays counted server-side before a URL exists; no plain audio stored; transcripts/answers never sent during an attempt; denied requests logged to `security_events` and abusive accounts flagged | `app/routers/media.py`, `app/services/protection.py` |
| Uploads | recordings: allowed audio types, 15 MB cap per part and per recording; CSV: 5 MB, UTF-8 only; imported media: size-capped download; learning hub files: extension allow-list checked against the file's first bytes, type set by the server, `RESOURCE_MAX_MB` cap; Caddy body limit 25 MB (110 MB for hub uploads only) | `config/ccl.yaml`, `app/services/imports`, `deploy/Caddyfile` |
| HTML | lesson HTML sanitised on write with an allow-list (nh3); links get `rel="noopener noreferrer nofollow"`; public copy is rendered as text | `app/services/html.py` |
| Payments | Stripe Checkout (no card data touches our servers); webhook signature verified; events processed once by id | `app/services/billing.py` |
| Secrets | all keys from `.env` (gitignored); production refuses to start with a short/default `SECRET_KEY`; a test scans tracked files for common key formats | `app/settings.py`, `tests/test_security.py` |
| Transport / headers | Caddy: automatic HTTPS, HSTS; app: `X-Content-Type-Options`, `X-Frame-Options: DENY` (hub files: `SAMEORIGIN`, so a PDF can be shown inside the hub page), `Referrer-Policy`, `Cache-Control: no-store` on API responses; mic-only Permissions-Policy | `deploy/Caddyfile`, `app/middleware.py`, `frontend/next.config.ts` |
| API docs | `/api/docs` and the OpenAPI schema are disabled in production | `app/main.py` |
| Open redirects | post-login `next` must be a same-site path | `frontend/src/lib/api.ts` |

Admin settings (Settings page): the SMTP password and Resend key are encrypted at rest with a key derived from
SECRET_KEY, are write-only in the API and never returned; changing SECRET_KEY makes them unreadable (the page says so
and asks for them again). Theme names reject markup; logos are checked by their first bytes (no SVG). An admin can point
SMTP at any host, so only trusted people should be admins.

Known limits: rate limits are per process (fine for one server; use Redis if the backend is scaled across hosts).
A student who can play audio can still record it from their sound card; per-user audio watermarking is a possible
later addition.
