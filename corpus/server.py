"""
Corpus FastAPI application factory and server entry point.

Usage:
    python -m corpus                      # run via __main__.py
    uvicorn corpus.server:app --reload    # development
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from corpus import config, log
from corpus.api import admin as admin_api
from corpus.api import checkpoints as checkpoints_api
from corpus.api import dashboard as dashboard_api
from corpus.api import gravity as gravity_api
from corpus.api import guardian as guardian_api
from corpus.api import memory as memory_api
from corpus.api import orchestration as orchestration_api
from corpus.api import policy as policy_api
from corpus.api import presence as presence_api
from corpus.api import products as products_api
from corpus.api import signals as signals_api
from corpus.api import translation as translation_api
from corpus.api import websocket as websocket_api
from corpus.security.auth import APIKeyMiddleware
from corpus.security.rate_limiter import RateLimiterMiddleware
from corpus.container import CorpusContainer
from corpus.errors import (
    CorpusError,
    ProductAlreadyRegisteredError,
    ProductNotFoundError,
    SignalAcknowledgementError,
    SignalExpiredError,
    SignalNotFoundError,
    SignalRoutingError,
)
from corpus.storage.database import init_db

log.configure()


def _make_lifespan(db_path: str):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger = log.get_logger("corpus.server")
        logger.info("corpus.starting", db=db_path)

        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await init_db(conn)

        container = CorpusContainer(conn)
        app.state.container = container

        # Start heartbeat monitor background task
        await container.heartbeat_monitor.start()

        logger.info("corpus.ready")
        try:
            yield
        finally:
            await container.heartbeat_monitor.stop()
            await conn.close()
            logger.info("corpus.stopped")

    return lifespan


def create_app(db_path: str | None = None) -> FastAPI:
    resolved_db = db_path if db_path is not None else config.DB_PATH

    app = FastAPI(
        title="Corpus",
        description="AI-native coordination and mediation layer between autonomous software systems",
        version=config.VERSION,
        lifespan=_make_lifespan(resolved_db),
    )

    # --- Routers ---
    app.include_router(products_api.router, prefix="/products", tags=["products"])
    app.include_router(signals_api.router, prefix="/signals", tags=["signals"])
    app.include_router(checkpoints_api.router)
    app.include_router(presence_api.router)
    app.include_router(websocket_api.router)
    app.include_router(gravity_api.router)
    app.include_router(translation_api.router)
    app.include_router(memory_api.router)
    app.include_router(policy_api.router)
    app.include_router(orchestration_api.router)
    app.include_router(guardian_api.router)
    app.include_router(dashboard_api.router)
    app.include_router(admin_api.router)

    # Optional security middleware (disabled by default for local dev)
    app.add_middleware(RateLimiterMiddleware.from_env)
    app.add_middleware(APIKeyMiddleware.from_env)

    # --- Health ---
    @app.get("/health", tags=["system"])
    async def health(request: Request) -> dict:
        return await request.app.state.container.runtime_service.get_health()

    # --- Exception handlers ---
    @app.exception_handler(ProductAlreadyRegisteredError)
    async def _h_already_registered(request: Request, exc: ProductAlreadyRegisteredError):
        return JSONResponse(status_code=409, content={"error": "conflict", "message": str(exc)})

    @app.exception_handler(ProductNotFoundError)
    async def _h_product_not_found(request: Request, exc: ProductNotFoundError):
        return JSONResponse(status_code=404, content={"error": "not_found", "message": str(exc)})

    @app.exception_handler(SignalNotFoundError)
    async def _h_signal_not_found(request: Request, exc: SignalNotFoundError):
        return JSONResponse(status_code=404, content={"error": "not_found", "message": str(exc)})

    @app.exception_handler(SignalExpiredError)
    async def _h_signal_expired(request: Request, exc: SignalExpiredError):
        return JSONResponse(status_code=410, content={"error": "gone", "message": str(exc)})

    @app.exception_handler(SignalRoutingError)
    async def _h_routing_error(request: Request, exc: SignalRoutingError):
        return JSONResponse(
            status_code=422, content={"error": "routing_error", "message": str(exc)}
        )

    @app.exception_handler(SignalAcknowledgementError)
    async def _h_ack_error(request: Request, exc: SignalAcknowledgementError):
        return JSONResponse(
            status_code=422, content={"error": "ack_error", "message": str(exc)}
        )

    @app.exception_handler(CorpusError)
    async def _h_corpus_error(request: Request, exc: CorpusError):
        return JSONResponse(
            status_code=400, content={"error": "corpus_error", "message": str(exc)}
        )

    return app


# Module-level app instance for uvicorn / `python -m corpus`
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("corpus.server:app", host=config.HOST, port=config.PORT, reload=False)
