"""Simple in-memory token-bucket rate limiter (optional)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Per-IP token-bucket rate limiter.

    Disabled by default for local dev. Set CORPUS_RATE_LIMIT_ENABLED=true
    and CORPUS_RATE_LIMIT_RPS=N to enable.
    """

    def __init__(
        self,
        app,
        enabled: bool = False,
        requests_per_second: float = 10.0,
        burst: int = 20,
    ) -> None:
        super().__init__(app)
        self._enabled = enabled
        self._rps = requests_per_second
        self._burst = burst
        # client_ip → (tokens, last_refill_time)
        self._buckets: dict[str, list] = defaultdict(lambda: [burst, time.monotonic()])

    @classmethod
    def from_env(cls, app) -> "RateLimiterMiddleware":
        enabled = os.getenv("CORPUS_RATE_LIMIT_ENABLED", "false").lower() == "true"
        rps = float(os.getenv("CORPUS_RATE_LIMIT_RPS", "10"))
        return cls(app, enabled=enabled, requests_per_second=rps)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self._enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket = self._buckets[client_ip]
        now = time.monotonic()
        elapsed = now - bucket[1]
        bucket[0] = min(self._burst, bucket[0] + elapsed * self._rps)
        bucket[1] = now

        if bucket[0] < 1:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "message": "Too many requests"},
            )
        bucket[0] -= 1
        return await call_next(request)
