"""Security middleware and utilities.

Covers:
  - API-key authentication (X-API-Key header, hmac.compare_digest)
  - In-memory token-bucket rate limiter (per client IP)
  - Global concurrency semaphore around LLM / Hindsight calls
  - Daily / monthly call counters
  - Security-header middleware (CSP, X-Content-Type-Options, etc.)
  - Request body size limit (256 KB)
  - Startup guard: refuse to bind non-loopback host without APP_API_KEY
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import threading
import time
from collections import defaultdict
from typing import Callable, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_API_KEY_HEADER = "X-API-Key"
_BODY_SIZE_LIMIT = 256 * 1024  # 256 KB

# Routes that do NOT require authentication
_AUTH_EXEMPT = frozenset({"/api/health"})

# Rate-limit tiers (requests per 60-second window)
_TIER_SLOW = 5    # analyze, compare, reflect
_TIER_MED = 30    # all other POSTs
_TIER_FAST = 120  # GETs (conservative guard)

# Slow routes (full path prefix match)
_SLOW_ROUTE_SUFFIXES = frozenset({
    "/analyze",
    "/compare",
    "/reflect",
})

# Global concurrency semaphore — LLM + Hindsight calls share this budget
_DEFAULT_CONCURRENCY = 4
_global_semaphore: threading.Semaphore = threading.Semaphore(
    getattr(settings, "max_concurrent_calls", _DEFAULT_CONCURRENCY)
)


def acquire_global_slot() -> bool:
    """Acquire a concurrency slot (non-blocking).  Returns False if full."""
    return _global_semaphore.acquire(blocking=False)


def release_global_slot() -> None:
    _global_semaphore.release()


# ---------------------------------------------------------------------------
# Startup guard
# ---------------------------------------------------------------------------


def check_startup_safety(host: str) -> None:
    """Raise RuntimeError if binding to a non-loopback address without APP_API_KEY."""
    if settings.environment.lower() == "development":
        return  # development mode: no key required regardless of host

    api_key = getattr(settings, "app_api_key", "") or ""
    if api_key:
        return  # key configured — safe to bind anywhere

    # Check whether host resolves to a loopback address
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_loopback:
            return
    except ValueError:
        if host in ("localhost", "127.0.0.1", "::1"):
            return

    raise RuntimeError(
        f"Refusing to start: host={host!r} is not loopback but APP_API_KEY is not set. "
        "Set APP_API_KEY in backend/.env before binding to a non-loopback address."
    )


# ---------------------------------------------------------------------------
# In-memory token bucket rate limiter
# ---------------------------------------------------------------------------


class _TokenBucket:
    """Thread-safe token bucket for a single client."""

    __slots__ = ("capacity", "tokens", "refill_rate", "_lock", "_last")

    def __init__(self, capacity: int, window_seconds: float = 60.0) -> None:
        self.capacity = capacity
        self.tokens: float = float(capacity)
        self.refill_rate: float = capacity / window_seconds  # tokens/second
        self._lock = threading.Lock()
        self._last: float = time.monotonic()

    def consume(self, cost: int = 1) -> tuple[bool, float]:
        """Try to consume *cost* tokens. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._last
            self._last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens >= cost:
                self.tokens -= cost
                return True, 0.0
            retry_after = (cost - self.tokens) / self.refill_rate
            return False, retry_after


class RateLimiter:
    """Per-IP token bucket registry with automatic cleanup."""

    def __init__(self) -> None:
        self._buckets: Dict[str, Dict[int, _TokenBucket]] = defaultdict(dict)
        self._lock = threading.Lock()

    def _bucket(self, client_ip: str, capacity: int) -> _TokenBucket:
        with self._lock:
            if capacity not in self._buckets[client_ip]:
                self._buckets[client_ip][capacity] = _TokenBucket(capacity)
            return self._buckets[client_ip][capacity]

    def check(self, client_ip: str, capacity: int, cost: int = 1) -> tuple[bool, float]:
        return self._bucket(client_ip, capacity).consume(cost)


_rate_limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    """Best-effort client IP; trusts X-Forwarded-For only in non-development."""
    xff = request.headers.get("x-forwarded-for")
    if xff and settings.environment.lower() != "development":
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _route_capacity(path: str, method: str) -> tuple[int, int]:
    """Return (capacity, cost) for the given path + method."""
    if method == "GET":
        return _TIER_FAST, 1
    # POST
    for suffix in _SLOW_ROUTE_SUFFIXES:
        if path.endswith(suffix):
            # compare counts double (runs two analyses)
            cost = 2 if path.endswith("/compare") else 1
            return _TIER_SLOW, cost
    return _TIER_MED, 1


# ---------------------------------------------------------------------------
# Daily / monthly counter
# ---------------------------------------------------------------------------


class _CallCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._daily: int = 0
        self._monthly: int = 0
        self._day: int = 0
        self._month: int = 0

    def _reset_if_needed(self) -> None:
        import datetime
        now = datetime.datetime.utcnow()
        with self._lock:
            if now.day != self._day:
                self._daily = 0
                self._day = now.day
            if now.month != self._month:
                self._monthly = 0
                self._month = now.month

    def increment(self) -> bool:
        """Increment counters. Returns True if the call is within limits."""
        self._reset_if_needed()
        daily_limit = getattr(settings, "max_daily_calls", 0)
        monthly_limit = getattr(settings, "max_monthly_calls", 0)
        with self._lock:
            if daily_limit and self._daily >= daily_limit:
                return False
            if monthly_limit and self._monthly >= monthly_limit:
                return False
            self._daily += 1
            self._monthly += 1
            return True

    @property
    def daily(self) -> int:
        self._reset_if_needed()
        return self._daily

    @property
    def monthly(self) -> int:
        self._reset_if_needed()
        return self._monthly


call_counter = _CallCounter()


# ---------------------------------------------------------------------------
# Middleware helpers
# ---------------------------------------------------------------------------


def _req_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def _is_api_route(path: str) -> bool:
    return path.startswith("/api/")


def _json_error(status: int, detail: str, request: Request,
                extra_headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    headers = {"X-Request-ID": _req_id(request)}
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(
        status_code=status,
        content={"detail": detail, "request_id": _req_id(request)},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# API-key auth middleware
# ---------------------------------------------------------------------------


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key on all /api/* routes except exempted ones.

    In development mode with no APP_API_KEY configured, auth is bypassed
    (allows offline development without setting a key).
    """

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path

        if not _is_api_route(path) or path in _AUTH_EXEMPT:
            return await call_next(request)

        configured_key = getattr(settings, "app_api_key", "") or ""

        # Development shortcut: if no key is configured AND env==development, skip
        if not configured_key and settings.environment.lower() == "development":
            return await call_next(request)

        if not configured_key:
            # Key required but not configured — refuse all requests
            return _json_error(500, "API key not configured on the server.", request)

        supplied = request.headers.get(_API_KEY_HEADER, "")
        if not supplied or not hmac.compare_digest(
            configured_key.encode("utf-8"), supplied.encode("utf-8")
        ):
            logger.warning(
                "Auth failure [request_id=%s] path=%s ip=%s",
                _req_id(request), path, _client_ip(request),
            )
            return _json_error(401, "Invalid or missing X-API-Key header.", request)

        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate-limit middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP token bucket rate limiting for /api/* routes."""

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        if not _is_api_route(path):
            return await call_next(request)

        ip = _client_ip(request)
        capacity, cost = _route_capacity(path, request.method)
        allowed, retry_after = _rate_limiter.check(ip, capacity, cost)

        if not allowed:
            ra = int(retry_after) + 1
            logger.info(
                "Rate limited [request_id=%s] ip=%s path=%s retry_after=%ds",
                _req_id(request), ip, path, ra,
            )
            return _json_error(
                429,
                f"Rate limit exceeded. Retry after {ra} seconds.",
                request,
                {"Retry-After": str(ra)},
            )

        # Daily/monthly limiter (only for expensive slow calls)
        if capacity == _TIER_SLOW:
            if not call_counter.increment():
                return _json_error(
                    429,
                    "Service call budget exceeded for today/this month. Try again later.",
                    request,
                )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Body size middleware
# ---------------------------------------------------------------------------


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds _BODY_SIZE_LIMIT (256 KB).

    Uses the raw ASGI scope/receive/send pattern to avoid BaseHTTPMiddleware's
    body-re-injection complexity.
    """

    def __init__(self, app: ASGIApp) -> None:
        # Don't call BaseHTTPMiddleware.__init__; we override __call__ directly.
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check Content-Length first (fast path)
        headers = dict(scope.get("headers", []))
        cl_raw = headers.get(b"content-length", b"")
        try:
            cl = int(cl_raw)
            if cl > _BODY_SIZE_LIMIT:
                await self._send_413(send)
                return
        except (ValueError, TypeError):
            pass  # no / unparseable Content-Length — check during stream

        # Buffer and enforce size limit
        body_parts: list[bytes] = []
        total = 0
        more_body = True

        while more_body:
            message = await receive()
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > _BODY_SIZE_LIMIT:
                await self._send_413(send)
                return
            body_parts.append(chunk)
            more_body = message.get("more_body", False)

        body = b"".join(body_parts)

        # Provide the already-read body back to the app
        body_iter = iter([{"type": "http.request", "body": body, "more_body": False}])

        async def _replay_receive():
            return next(body_iter)

        await self.app(scope, _replay_receive, send)

    @staticmethod
    async def _send_413(send):
        import json as _json
        body = _json.dumps(
            {"detail": f"Request body exceeds the {_BODY_SIZE_LIMIT // 1024} KB limit."}
        ).encode()
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response
