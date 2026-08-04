from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import get_settings
from .db import SessionLocal
from .logging import get_logger
from .models import AuditLog
from .security import TokenType, decode_token

logger = get_logger(__name__)
settings = get_settings()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or secrets.token_hex(12)
        request.state.request_id = request_id
        started = time.perf_counter()
        response: Response
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "http_request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
        response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["content-security-policy"] = "default-src 'none'; frame-ancestors 'none'"
        if settings.is_production:
            response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
        return response


class LocalRateLimitMiddleware(BaseHTTPMiddleware):
    """Best-effort instance-level limiter. Production edge/WAF remains authoritative."""

    def __init__(self, app: Any, requests_per_minute: int = 240) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._last_cleanup = time.monotonic()

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < 60:
            return
        stale_before = now - 60
        for client, hits in list(self._hits.items()):
            while hits and hits[0] <= stale_before:
                hits.popleft()
            if not hits:
                self._hits.pop(client, None)
        self._last_cleanup = now

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in {
            "/api/v1/health",
            "/api/v1/live",
            "/api/v1/ready",
            "/metrics",
            "/metrics/",
        }:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        self._cleanup(now)
        window = self._hits[client]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "type": "https://api.macrolens.local/problems/rate-limit",
                    "title": "请求过于频繁",
                    "status": 429,
                    "detail": "请稍后重试。生产环境还应在边缘网关配置分布式限流。",
                    "code": "rate_limit_exceeded",
                },
                headers={"Retry-After": "60"},
            )
        window.append(now)
        return await call_next(request)


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin state-changing cookie-auth requests before routing."""

    def __init__(self, app: Any, allowed_origin: str) -> None:
        super().__init__(app)
        self.allowed_origin = allowed_origin.rstrip("/")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            return await call_next(request)
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        candidate = origin or (referer.rstrip("/") if referer else None)
        has_auth_cookie = bool(
            request.cookies.get("macrolens_access") or request.cookies.get("macrolens_refresh")
        )
        if (has_auth_cookie and not candidate) or (
            candidate
            and not (
                candidate == self.allowed_origin or candidate.startswith(f"{self.allowed_origin}/")
            )
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "type": "https://api.macrolens.local/problems/csrf-origin",
                    "title": "请求来源无效",
                    "status": 403,
                    "detail": "状态变更请求必须来自已配置的 Web 站点。",
                    "code": "csrf_origin_rejected",
                },
            )
        return await call_next(request)


class DemoReadOnlyMiddleware(BaseHTTPMiddleware):
    """Fail closed for API mutations while serving deterministic demo data."""

    _AUTH_SESSION_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/refresh",
    }

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if (
            settings.data_mode == "demo"
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path not in self._AUTH_SESSION_PATHS
        ):
            return JSONResponse(
                status_code=409,
                content={
                    "type": "https://api.macrolens.local/problems/demo-read-only",
                    "title": "Demo data mode is read-only",
                    "status": 409,
                    "detail": "State-changing API operations are disabled in demo data mode.",
                    "code": "demo_read_only",
                },
            )
        return await call_next(request)


class AuditMiddleware(BaseHTTPMiddleware):
    """Best-effort immutable audit trail for successful state-changing API requests."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or response.status_code >= 400:
            return response
        actor_user_id = None
        token = request.cookies.get("macrolens_access")
        if token:
            try:
                actor_user_id = decode_token(token, TokenType.ACCESS).sub
            except Exception:
                actor_user_id = None
        try:
            async with SessionLocal() as session:
                assert isinstance(session, AsyncSession)
                session.add(
                    AuditLog(
                        actor_user_id=actor_user_id,
                        action=request.method.lower(),
                        object_type=request.url.path,
                        object_id=None,
                        request_id=getattr(request.state, "request_id", None),
                        ip_address=request.client.host if request.client else None,
                    )
                )
                await session.commit()
        except Exception as exc:
            logger.warning("audit_write_failed", path=request.url.path, error=str(exc))
        return response
