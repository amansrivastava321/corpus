"""GravityClient — evaluate signal gravity via the Corpus API."""

from __future__ import annotations

from typing import Any

from corpus_sdk.transport import BaseTransport


class GravityResult:
    def __init__(self, data: dict[str, Any]) -> None:
        self.signal_id: str = data["signal_id"]
        self.score: float = data["score"]
        self.action: str = data["action"]
        self.explanation: str = data["explanation"]
        self.confidence: float = data["confidence"]
        self.evidence: list[str] = data.get("evidence", [])
        self.is_blocking: bool = data["is_blocking"]
        self.requires_checkpoint: bool = data["requires_checkpoint"]

    def __repr__(self) -> str:
        return f"GravityResult(score={self.score:.2f}, action={self.action}, confidence={self.confidence:.2f})"


class GravityClient:
    def __init__(self, transport: BaseTransport) -> None:
        self._transport = transport

    def evaluate(
        self,
        signal: dict[str, Any],
        *,
        has_active_checkpoint: bool = False,
        target_online: bool = True,
        source_trust: float = 0.8,
        historical_block_count: int = 0,
    ) -> GravityResult:
        resp = self._transport.post(
            "/gravity/evaluate",
            {
                "signal": signal,
                "has_active_checkpoint": has_active_checkpoint,
                "target_online": target_online,
                "source_trust": source_trust,
                "historical_block_count": historical_block_count,
            },
        )
        return GravityResult(resp)
