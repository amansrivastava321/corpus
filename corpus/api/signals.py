"""Signal emit, pending, ack, and inspect routes."""

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from corpus.dependencies import get_signal_service
from corpus.schemas import Signal
from corpus.services.signal_service import SignalService

logger = structlog.get_logger()

router = APIRouter()


class AckRequest(BaseModel):
    product_id: str


class AckResponse(BaseModel):
    status: str
    signal_id: str
    product_id: str


@router.post("/emit", response_model=Signal, status_code=202)
async def emit_signal(
    signal: Signal,
    service: SignalService = Depends(get_signal_service),
) -> Signal:
    return await service.emit(signal)


@router.get("/pending/{product_id}", response_model=list[Signal])
async def get_pending(
    product_id: str,
    service: SignalService = Depends(get_signal_service),
) -> list[Signal]:
    return await service.get_pending(product_id)


@router.post("/{signal_id}/ack", response_model=AckResponse)
async def acknowledge(
    signal_id: str,
    body: AckRequest,
    service: SignalService = Depends(get_signal_service),
) -> AckResponse:
    await service.acknowledge(signal_id, body.product_id)
    return AckResponse(status="acknowledged", signal_id=signal_id, product_id=body.product_id)


@router.get("/{signal_id}", response_model=Signal)
async def get_signal(
    signal_id: str,
    service: SignalService = Depends(get_signal_service),
) -> Signal:
    return await service.get(signal_id)
