"""Simple in-memory sliding-window rate limiter."""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Enforce per-IP request limits using a sliding time window.

    Not suitable for multi-process deployments — use Redis-backed
    limiting in production clusters.
    """

    def __init__(self, app, *, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window_seconds

        timestamps = self._hits[client_ip]
        self._hits[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._hits[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "detail": (
                        f"Max {self.max_requests} requests "
                        f"per {self.window_seconds}s exceeded"
                    ),
                    "status_code": 429,
                },
            )

        self._hits[client_ip].append(now)
        return await call_next(request)
