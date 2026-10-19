"""Password hashing and session tokens (from the demo: PBKDF2 + HS256 JWT in an httpOnly cookie)."""
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from .settings import get_settings

COOKIE_NAME = "ccl_session"
_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
    return f"pbkdf2${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check, digest)


def issue_session_token(user_id: str, role: str) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": secrets.token_hex(12),  # login session id; media grants are bound to it
        "exp": datetime.now(UTC) + timedelta(hours=s.session_hours),
    }
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def new_reset_token() -> tuple[str, str]:
    """Returns (token for the email link, sha256 hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
