"""TranslationClient — translate signal payloads via the Corpus API."""

from __future__ import annotations

from typing import Any

from corpus_sdk.transport import BaseTransport


class TranslationResult:
    def __init__(self, data: dict[str, Any]) -> None:
        self.signal_id: str = data.get("signal_id", "")
        self.source_product: str = data["source_product"]
        self.target_product: str = data["target_product"]
        self.original_payload: dict = data["original_payload"]
        self.translated_payload: dict = data["translated_payload"]
        self.confidence: float = data["confidence"]
        self.method: str = data["method"]
        self.explanation: str = data.get("explanation", "")
        self.warnings: list[str] = data.get("warnings", [])
        self.is_high_confidence: bool = data.get("is_high_confidence", False)

    def __repr__(self) -> str:
        return f"TranslationResult(method={self.method}, confidence={self.confidence:.2f})"


class TranslationClient:
    def __init__(self, transport: BaseTransport) -> None:
        self._transport = transport

    def translate(
        self,
        source_product: str,
        target_product: str,
        payload: dict[str, Any],
        *,
        signal_id: str = "",
        signal_type: str = "",
        severity: str = "",
    ) -> TranslationResult:
        resp = self._transport.post(
            "/translation/translate",
            {
                "signal_id": signal_id,
                "source_product": source_product,
                "target_product": target_product,
                "payload": payload,
                "signal_type": signal_type,
                "severity": severity,
            },
        )
        return TranslationResult(resp)
