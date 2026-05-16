"""TranslationResult — structured output from a translation operation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TranslationResult:
    source_product: str
    target_product: str
    original_payload: dict
    translated_payload: dict
    confidence: float
    method: str          # "llm", "intent_map", "fallback"
    explanation: str = ""
    warnings: list[str] = field(default_factory=list)
    signal_id: str = ""

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.80
