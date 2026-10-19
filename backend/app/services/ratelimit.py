"""In-memory sliding-window rate limiter (per process). Enough for one Hetzner box; swap for Redis if we scale out."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_windows: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def hit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Record one hit; True if the key is now over its limit."""
    now = time.monotonic()
    with _lock:
        q = _windows[key]
        while q and q[0] < now - window_seconds:
            q.popleft()
        q.append(now)
        return len(q) > limit


def enforce(key: str, limit: int, window_seconds: int = 60) -> None:
    if hit(key, limit, window_seconds):
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")


def reset() -> None:
    with _lock:
        _windows.clear()
