"""TranslationEngine — orchestrates LLM (optional) and deterministic fallback."""

from __future__ import annotations

import json
import logging

from corpus.translation.fallback_translator import FallbackTranslator
from corpus.translation.product_profile import get_profile
from corpus.translation.structured_output import TranslationResult
from corpus.translation.translation_prompt_registry import build_prompt

_log = logging.getLogger(__name__)


class TranslationEngine:
    """
    Translation pipeline:
    1. If Ollama is reachable → ask LLM, validate JSON output
    2. If LLM unavailable or output invalid → FallbackTranslator
    """

    def __init__(self, ollama_url: str | None = None, model: str = "llama3") -> None:
        self._ollama_url = ollama_url
        self._model = model
        self._fallback = FallbackTranslator()

    def translate(
        self,
        signal_id: str,
        source_product: str,
        target_product: str,
        original_payload: dict,
        signal_type: str = "",
        severity: str = "",
    ) -> TranslationResult:
        if self._ollama_url:
            result = self._try_llm(
                signal_id, source_product, target_product,
                original_payload, signal_type, severity,
            )
            if result is not None:
                return result

        return self._fallback.translate(
            signal_id, source_product, target_product,
            original_payload, signal_type, severity,
        )

    def _try_llm(
        self,
        signal_id: str,
        source_product: str,
        target_product: str,
        original_payload: dict,
        signal_type: str,
        severity: str,
    ) -> TranslationResult | None:
        try:
            import urllib.request

            source_profile = get_profile(source_product)
            target_profile = get_profile(target_product)

            system_prompt, user_prompt = build_prompt(
                source_product=source_profile.product_name,
                source_style=source_profile.style_description,
                target_product=target_profile.product_name,
                target_style=target_profile.style_description,
                signal_type=signal_type,
                severity=severity,
                payload_json=json.dumps(original_payload, indent=2),
            )

            body = json.dumps({
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            }).encode()

            req = urllib.request.Request(
                f"{self._ollama_url}/api/chat",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            content = data["message"]["content"].strip()
            # Extract JSON block if wrapped in ```
            if "```" in content:
                start = content.index("{")
                end = content.rindex("}") + 1
                content = content[start:end]

            translated = json.loads(content)
            if not isinstance(translated, dict):
                raise ValueError("LLM returned non-dict JSON")

            return TranslationResult(
                source_product=source_product,
                target_product=target_product,
                original_payload=original_payload,
                translated_payload=translated,
                confidence=0.90,
                method="llm",
                explanation=f"Translated via Ollama {self._model}",
                signal_id=signal_id,
            )

        except Exception as exc:
            _log.debug("llm_translation_failed", extra={"error": str(exc)})
            return None
