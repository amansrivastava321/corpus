"""API key authentication middleware (optional — disabled in local dev mode)."""

from __future__ import annotations

import os
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Validates X-API-Key header on all non-health requests.

    Bypass: set CORPUS_AUTH_ENABLED=false (default) to disable for local dev.
    Keys:   set CORPUS_API_KEYS=key1,key2,... to configure valid keys.

    Public paths: /health, /docs, /openapi.json always pass through.
    """

    _PUBLIC = {"/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app, valid_keys: set[str] | None = None, enabled: bool = False) -> None:
        super().__init__(app)
        self._keys = valid_keys or set()
        self._enabled = enabled

    @classmethod
    def from_env(cls, app) -> "APIKeyMiddleware":
        enabled = os.getenv("CORPUS_AUTH_ENABLED", "false").lower() == "true"
        raw = os.getenv("CORPUS_API_KEYS", "")
        keys = {k.strip() for k in raw.split(",") if k.strip()}
        return cls(app, valid_keys=keys, enabled=enabled)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self._enabled:
            return await call_next(request)

        if request.url.path in self._PUBLIC:
            return await call_next(request)

        key = request.headers.get("X-API-Key", "")
        if key not in self._keys:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Invalid or missing API key"},
            )
        return await call_next(request)
