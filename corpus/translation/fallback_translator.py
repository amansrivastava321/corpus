"""FallbackTranslator — rule-based translation when no LLM is available."""

from __future__ import annotations

from corpus.translation.intent_mapper import IntentMapper
from corpus.translation.product_profile import get_profile
from corpus.translation.structured_output import TranslationResult


class FallbackTranslator:
    """
    Deterministic fallback used when Ollama / LLM is unavailable.
    Applies IntentMapper and enriches with target-profile context.
    """

    def __init__(self) -> None:
        self._mapper = IntentMapper()

    def translate(
        self,
        signal_id: str,
        source_product: str,
        target_product: str,
        original_payload: dict,
        signal_type: str = "",
        severity: str = "",
    ) -> TranslationResult:
        translated, confidence, explanation = self._mapper.map(
            original_payload, source_product, target_product
        )

        # Enrich with signal-level metadata the target might not know
        translated["_corpus_signal_type"] = signal_type
        translated["_corpus_severity"] = severity
        translated["_corpus_source"] = source_product

        target_profile = get_profile(target_product)
        warnings: list[str] = []
        for field in target_profile.expected_payload_fields:
            if translated.get(field) is None:
                warnings.append(f"Expected field '{field}' could not be populated")

        return TranslationResult(
            source_product=source_product,
            target_product=target_product,
            original_payload=original_payload,
            translated_payload=translated,
            confidence=confidence,
            method="fallback",
            explanation=explanation,
            warnings=warnings,
            signal_id=signal_id,
        )
