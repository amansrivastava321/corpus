"""Translation API — translate signal payloads between product vocabularies."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/translation", tags=["translation"])


class TranslationRequest(BaseModel):
    signal_id: str = ""
    source_product: str
    target_product: str
    payload: dict
    signal_type: str = ""
    severity: str = ""


class TranslationResponse(BaseModel):
    signal_id: str
    source_product: str
    target_product: str
    original_payload: dict
    translated_payload: dict
    confidence: float
    method: str
    explanation: str
    warnings: list[str]
    is_high_confidence: bool


@router.post("/translate", response_model=TranslationResponse, status_code=200)
async def translate_signal(request_data: TranslationRequest, request: Request) -> TranslationResponse:
    container = request.app.state.container
    result = container.translator.translate(
        signal_id=request_data.signal_id,
        source_product=request_data.source_product,
        target_product=request_data.target_product,
        original_payload=request_data.payload,
        signal_type=request_data.signal_type,
        severity=request_data.severity,
    )
    return TranslationResponse(
        signal_id=result.signal_id,
        source_product=result.source_product,
        target_product=result.target_product,
        original_payload=result.original_payload,
        translated_payload=result.translated_payload,
        confidence=result.confidence,
        method=result.method,
        explanation=result.explanation,
        warnings=result.warnings,
        is_high_confidence=result.is_high_confidence,
    )
