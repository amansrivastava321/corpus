"""Dashboard API — observability endpoints for all Corpus subsystems."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_summary()


@router.get("/timeline")
async def get_timeline(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    return await request.app.state.container.dashboard_service.get_timeline(limit)


@router.get("/products")
async def get_products(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_products()


@router.get("/signals")
async def get_signals(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_signals()


@router.get("/checkpoints")
async def get_checkpoints(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_checkpoints()


@router.get("/orchestrations")
async def get_orchestrations(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_orchestrations()


@router.get("/guardian")
async def get_guardian(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_guardian()


@router.get("/memory")
async def get_memory(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_memory()


@router.get("/audit")
async def get_audit(request: Request) -> dict:
    return await request.app.state.container.dashboard_service.get_audit()
