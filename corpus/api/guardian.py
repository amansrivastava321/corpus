"""Guardian API — proactive intervention and risk evaluation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/guardian", tags=["guardian"])


class EvaluateRequest(BaseModel):
    signal: dict
    gravity_action: str = "ALLOW"


class SetModeRequest(BaseModel):
    mode: str  # OBSERVE_ONLY | ADVISOR | GUARDIAN
    dry_run: bool = False


@router.get("/status")
async def get_status(request: Request) -> dict:
    return await request.app.state.container.guardian_engine.get_status()


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest, request: Request) -> dict:
    container = request.app.state.container
    from corpus.schemas import Signal
    try:
        sig = Signal.model_validate(req.signal)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid signal: {exc}") from exc

    intervention = await container.guardian_engine.evaluate(sig, req.gravity_action)
    return intervention.to_dict()


@router.post("/mode")
async def set_mode(req: SetModeRequest, request: Request) -> dict:
    from corpus.guardian.guardian_models import GuardianMode
    try:
        mode = GuardianMode(req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid mode: {req.mode}") from exc
    container = request.app.state.container
    container.guardian_engine.set_mode(mode)
    container.guardian_engine._dry_run = req.dry_run
    return {"status": "ok", "mode": mode.value, "dry_run": req.dry_run}


@router.get("/interventions")
async def list_interventions(
    request: Request,
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    container = request.app.state.container
    interventions = await container.guardian_engine._state.list_interventions(
        limit=limit, action=action
    )
    return {
        "interventions": [i.to_dict() for i in interventions],
        "count": len(interventions),
    }


@router.get("/interventions/{intervention_id}")
async def get_intervention(intervention_id: str, request: Request) -> dict:
    container = request.app.state.container
    iv = await container.guardian_engine._state.get_intervention(intervention_id)
    if iv is None:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return iv.to_dict()
