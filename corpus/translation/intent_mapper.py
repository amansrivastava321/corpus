"""IntentMapper — deterministic vocabulary-based intent translation."""

from __future__ import annotations

from corpus.translation.product_profile import ProductProfile, get_profile


class IntentMapper:
    """
    Maps payload fields from source vocabulary to target vocabulary using
    ProductProfile dictionaries. Fully deterministic — no LLM required.
    """

    def map(
        self,
        payload: dict,
        source_name: str,
        target_name: str,
    ) -> tuple[dict, float, str]:
        """
        Returns (translated_payload, confidence, explanation).
        """
        source_profile = get_profile(source_name)
        target_profile = get_profile(target_name)

        translated: dict = {}
        mappings_applied: list[str] = []

        for key, value in payload.items():
            # Check if this key has a known mapping in the target's vocabulary
            target_key = target_profile.vocabulary.get(key)
            if target_key:
                translated[target_key] = value
                mappings_applied.append(f"{key}→{target_key}")
            else:
                # Check if source uses this key in its own vocab → rephrase
                source_alias = source_profile.vocabulary.get(key, key)
                translated[source_alias] = value

        # Add expected fields that are missing (with None sentinel)
        for expected in target_profile.expected_payload_fields:
            if expected not in translated:
                translated.setdefault(expected, None)

        confidence = 0.75 if mappings_applied else 0.60
        explanation = (
            f"Intent mapped {len(mappings_applied)} field(s): {', '.join(mappings_applied)}"
            if mappings_applied
            else "Payload passed through with no vocabulary mapping"
        )
        return translated, confidence, explanation
