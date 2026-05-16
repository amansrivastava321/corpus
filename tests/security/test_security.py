"""Phase 12 — Security and hardening tests."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from corpus.security.auth import APIKeyMiddleware
from corpus.security.rate_limiter import RateLimiterMiddleware
from corpus.server import create_app


# ─── Auth middleware unit tests ───────────────────────────────────────────────

def _make_app_with_auth(keys: set, enabled: bool = True) -> FastAPI:
    from fastapi import FastAPI
    app = FastAPI()

    @app.get("/test")
    async def test_route() -> dict:
        return {"ok": True}

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    app.add_middleware(APIKeyMiddleware, valid_keys=keys, enabled=enabled)
    return app


class TestAPIKeyMiddleware:
    def test_valid_key_allows(self):
        app = _make_app_with_auth({"secret-key"})
        with TestClient(app) as c:
            resp = c.get("/test", headers={"X-API-Key": "secret-key"})
        assert resp.status_code == 200

    def test_invalid_key_rejects(self):
        app = _make_app_with_auth({"secret-key"})
        with TestClient(app) as c:
            resp = c.get("/test", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_missing_key_rejects(self):
        app = _make_app_with_auth({"secret-key"})
        with TestClient(app) as c:
            resp = c.get("/test")
        assert resp.status_code == 401

    def test_disabled_allows_all(self):
        app = _make_app_with_auth({"secret-key"}, enabled=False)
        with TestClient(app) as c:
            resp = c.get("/test")  # no key
        assert resp.status_code == 200

    def test_public_paths_bypass_auth(self):
        app = _make_app_with_auth({"secret-key"})
        with TestClient(app) as c:
            resp = c.get("/health")  # public path
        assert resp.status_code == 200


class TestRateLimiter:
    def _make_app(self, rps: float = 2.0, burst: int = 3) -> FastAPI:
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict:
            return {"ok": True}

        app.add_middleware(
            RateLimiterMiddleware,
            enabled=True,
            requests_per_second=rps,
            burst=burst,
        )
        return app

    def test_within_limit_allowed(self):
        app = self._make_app(rps=100.0, burst=100)
        with TestClient(app) as c:
            for _ in range(5):
                resp = c.get("/test")
                assert resp.status_code == 200

    def test_exceeds_burst_rate_limited(self):
        app = self._make_app(rps=0.1, burst=2)
        with TestClient(app, raise_server_exceptions=False) as c:
            responses = [c.get("/test") for _ in range(10)]
        # At least one should be rate limited (429)
        statuses = [r.status_code for r in responses]
        assert 429 in statuses

    def test_disabled_never_limits(self):
        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict:
            return {"ok": True}

        app.add_middleware(RateLimiterMiddleware, enabled=False)
        with TestClient(app) as c:
            for _ in range(20):
                resp = c.get("/test")
                assert resp.status_code == 200


# ─── Auth disabled in corpus server (local dev) ───────────────────────────────

class TestCorpusLocalDevNoAuth:
    def test_corpus_server_auth_disabled_by_default(self):
        """Auth is disabled by default — all routes accessible without key."""
        with TestClient(create_app(db_path=":memory:")) as c:
            resp = c.get("/health")
            assert resp.status_code == 200
            resp2 = c.get("/policy")
            assert resp2.status_code == 200
