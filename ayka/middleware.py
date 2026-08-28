"""Rate limiting middleware.

Per-IP sliding window. Multiproxy-aware: reads the leftmost real client IP from
`X-Forwarded-For` (written by cloudflared / nginx), so a tunnel in front does
not collapse every visitor into one bucket. Separate (stricter) pool for paths
that start with any of `protected_prefixes`.
"""
import time
from collections import defaultdict, deque
from typing import Iterable, Optional

from starlette.middleware.base import BaseHTTPMiddleware


def _client_ip(request) -> Optional[str]:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first and first != "unknown":
            return first
    if request.client is not None:
        return request.client.host
    return None


class RateLimiter:
    def __init__(
        self,
        max_requests: int = 120,
        window_seconds: int = 60,
        admin_max_requests: int = 30,
        protected_prefixes: Iterable[str] = ("/api/admin/",),
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.admin_max_requests = admin_max_requests
        self.prefixes = tuple(protected_prefixes)
        self._store: dict = defaultdict(deque)
        self._admin_store: dict = defaultdict(deque)

    def is_protected(self, path: str) -> bool:
        return path.startswith(self.prefixes)

    def allowed(self, key: str, *, protected: bool = False) -> bool:
        limit = self.admin_max_requests if protected else self.max_requests
        store = self._admin_store if protected else self._store
        now = time.monotonic()
        bucket = store[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def rate_limit_middleware(limiter: RateLimiter):
    """FastAPI/Starlette middleware factory tied to a RateLimiter instance."""

    class _RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            ip = _client_ip(request)
            if ip is not None and not limiter.allowed(ip, protected=limiter.is_protected(request.url.path)):
                from starlette.responses import JSONResponse, PlainTextResponse

                return PlainTextResponse("Rate limit exceeded", status_code=429)
            return await call_next(request)

    return _RateLimitMiddleware


__all__ = ["RateLimiter", "rate_limit_middleware", "_client_ip"]