"""Memory API — query episodic memory and trigger pattern mining."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/memory", tags=["memory"])


class RecallRequest(BaseModel):
    query: str
    source_product: str | None = None
    target_product: str | None = None
    top_k: int = 5


@router.get("/episodes")
async def list_episodes(
    request: Request,
    product: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    container = request.app.state.container
    episodes = await container.memory_service.list_episodes(product, status, limit)
    return {"episodes": episodes, "count": len(episodes)}


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: str, request: Request) -> dict:
    container = request.app.state.container
    episode = await container.memory_service.get_episode(episode_id)
    if episode is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@router.post("/recall")
async def recall(request_data: RecallRequest, request: Request) -> dict:
    container = request.app.state.container
    episodes = await container.memory_service.recall(
        query=request_data.query,
        source_product=request_data.source_product,
        target_product=request_data.target_product,
        top_k=request_data.top_k,
    )
    return {"episodes": episodes, "count": len(episodes)}


@router.post("/mine-patterns")
async def mine_patterns(request: Request) -> dict:
    container = request.app.state.container
    patterns = await container.memory_service.mine_patterns()
    return {"patterns": patterns, "count": len(patterns)}


@router.post("/snapshot")
async def snapshot(request: Request) -> dict:
    container = request.app.state.container
    await container.memory_service.snapshot_artifacts()
    return {"status": "ok", "message": "Artifacts written to artifacts/memory/"}
