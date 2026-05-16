"""Presence REST endpoints — query which products are currently connected."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from corpus.dependencies import get_ws_service

router = APIRouter(prefix="/presence", tags=["realtime"])


@router.get("")
async def list_presence(request: Request) -> list[dict]:
    """Return presence state for all products that have ever connected via WebSocket."""
    ws_service = get_ws_service(request)
    return ws_service.list_presence()


@router.get("/{product_id}")
async def get_presence(product_id: str, request: Request) -> dict:
    """Return presence state for a specific product."""
    ws_service = get_ws_service(request)
    presence = ws_service.get_presence(product_id)
    if presence is None:
        raise HTTPException(
            status_code=404,
            detail=f"No presence record for product '{product_id}'",
        )
    return presence
