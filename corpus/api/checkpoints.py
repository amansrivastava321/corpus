"""Checkpoint REST API — execution governance endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from corpus.dependencies import get_checkpoint_service

router = APIRouter(prefix="/checkpoints", tags=["checkpoints"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RegisterCheckpointRequest(BaseModel):
    product_id: str
    checkpoint_type: str
    context: dict[str, Any] = {}
    timeout_seconds: int | None = None
    timeout_policy: str = "FAIL_OPEN"


class ResolveResponse(BaseModel):
    checkpoint_id: str
    status: str
    resolved_at: str | None


def _checkpoint_to_dict(cp) -> dict:
    return {
        "id": cp.id,
        "product_id": cp.product_id,
        "product_name": cp.product_name,
        "checkpoint_type": cp.checkpoint_type,
        "status": cp.status.value,
        "timeout_policy": cp.timeout_policy.value,
        "context": cp.context,
        "created_at": cp.created_at.isoformat(),
        "updated_at": cp.updated_at.isoformat(),
        "resolved_at": cp.resolved_at.isoformat() if cp.resolved_at else None,
        "timeout_at": cp.timeout_at.isoformat() if cp.timeout_at else None,
        "decision_id": cp.decision_id,
    }


def _decision_to_dict(d) -> dict:
    return {
        "id": d.id,
        "checkpoint_id": d.checkpoint_id,
        "decision_type": d.decision_type.value,
        "reason": d.reason,
        "decided_by": d.decided_by,
        "trigger_signal_id": d.trigger_signal_id,
        "created_at": d.created_at.isoformat(),
        "is_blocking": d.is_blocking(),
        "allows_continuation": d.allows_continuation(),
        "metadata": d.metadata,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", status_code=201)
async def register_checkpoint(body: RegisterCheckpointRequest, request: Request) -> dict:
    """Register a new execution checkpoint."""
    svc = get_checkpoint_service(request)
    checkpoint = await svc.register(
        product_id=body.product_id,
        checkpoint_type=body.checkpoint_type,
        context=body.context,
        timeout_seconds=body.timeout_seconds,
        timeout_policy=body.timeout_policy,
    )
    return _checkpoint_to_dict(checkpoint)


@router.post("/{checkpoint_id}/request-clearance")
async def request_clearance(checkpoint_id: str, request: Request) -> dict:
    """Request a clearance decision for a checkpoint."""
    svc = get_checkpoint_service(request)
    decision = await svc.request_clearance(checkpoint_id)
    return _decision_to_dict(decision)


@router.post("/{checkpoint_id}/resolve")
async def resolve_checkpoint(checkpoint_id: str, request: Request) -> dict:
    """Mark a checkpoint as resolved — execution completed successfully."""
    svc = get_checkpoint_service(request)
    checkpoint = await svc.resolve(checkpoint_id)
    return _checkpoint_to_dict(checkpoint)


@router.post("/{checkpoint_id}/cancel")
async def cancel_checkpoint(checkpoint_id: str, request: Request) -> dict:
    """Cancel a checkpoint — product chose not to proceed."""
    svc = get_checkpoint_service(request)
    checkpoint = await svc.cancel(checkpoint_id)
    return _checkpoint_to_dict(checkpoint)


@router.get("/{checkpoint_id}")
async def get_checkpoint(checkpoint_id: str, request: Request) -> dict:
    """Get the current state of a checkpoint."""
    svc = get_checkpoint_service(request)
    checkpoint = await svc.get(checkpoint_id)
    return _checkpoint_to_dict(checkpoint)


@router.get("")
async def list_checkpoints(
    request: Request,
    product_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list[dict]:
    """List checkpoints, optionally filtered by product or status."""
    svc = get_checkpoint_service(request)
    checkpoints = await svc.list_all(product_id=product_id, status=status)
    return [_checkpoint_to_dict(cp) for cp in checkpoints]


@router.get("/{checkpoint_id}/history")
async def get_history(checkpoint_id: str, request: Request) -> list[dict]:
    """Get the full audit trail for a checkpoint."""
    svc = get_checkpoint_service(request)
    return await svc.get_history(checkpoint_id)


@router.get("/{checkpoint_id}/decision")
async def get_decision(checkpoint_id: str, request: Request) -> dict:
    """Get the latest clearance decision for a checkpoint."""
    svc = get_checkpoint_service(request)
    decision = await svc.get_decision(checkpoint_id)
    if decision is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "No decision yet for this checkpoint"},
        )
    return _decision_to_dict(decision)
