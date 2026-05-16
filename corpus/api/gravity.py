"""Gravity API — evaluate signal gravity on demand."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from corpus.gravity.gravity_score import GravityAction
from corpus.gravity.risk_context import RiskContext
from corpus.schemas import Signal

router = APIRouter(prefix="/gravity", tags=["gravity"])


class GravityRequest(BaseModel):
    signal: dict
    has_active_checkpoint: bool = False
    target_online: bool = True
    source_trust: float = 0.8
    historical_block_count: int = 0


class GravityResponse(BaseModel):
    signal_id: str
    score: float
    action: str
    explanation: str
    confidence: float
    evidence: list[str]
    is_blocking: bool
    requires_checkpoint: bool


@router.post("/evaluate", response_model=GravityResponse, status_code=200)
async def evaluate_gravity(request: GravityRequest) -> GravityResponse:
    container = None
    try:
        sig = Signal.model_validate(request.signal)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid signal: {exc}") from exc

    from corpus.gravity.gravity_engine import GravityEngine
    from corpus.gravity.risk_context import RiskContext

    ctx = RiskContext(
        has_active_checkpoint=request.has_active_checkpoint,
        target_online=request.target_online,
        source_trust=request.source_trust,
        historical_block_count=request.historical_block_count,
    )
    engine = GravityEngine()
    score = engine.evaluate(sig, ctx)

    return GravityResponse(
        signal_id=sig.id,
        score=score.score,
        action=score.action.value,
        explanation=score.explanation,
        confidence=score.confidence,
        evidence=score.evidence,
        is_blocking=score.action.is_blocking,
        requires_checkpoint=score.action.requires_checkpoint,
    )
