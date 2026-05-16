"""Translator — application-layer service wrapping TranslationEngine."""

from __future__ import annotations

import logging

from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEvent, CorpusEventType
from corpus.translation.structured_output import TranslationResult
from corpus.translation.translation_engine import TranslationEngine

_log = logging.getLogger(__name__)


class Translator:
    """
    Service facade for signal translation.  Used by the container and API layer.
    Emits SIGNAL_TRANSLATED events after each translation.
    """

    def __init__(
        self,
        engine: TranslationEngine | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._engine = engine or TranslationEngine()
        self._bus = event_bus

    def translate(
        self,
        signal_id: str,
        source_product: str,
        target_product: str,
        original_payload: dict,
        signal_type: str = "",
        severity: str = "",
    ) -> TranslationResult:
        result = self._engine.translate(
            signal_id=signal_id,
            source_product=source_product,
            target_product=target_product,
            original_payload=original_payload,
            signal_type=signal_type,
            severity=severity,
        )

        _log.debug(
            "signal_translated",
            extra={
                "signal_id": signal_id,
                "method": result.method,
                "confidence": result.confidence,
            },
        )

        if self._bus is not None:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._emit(result))
            except RuntimeError:
                pass

        return result

    async def translate_async(
        self,
        signal_id: str,
        source_product: str,
        target_product: str,
        original_payload: dict,
        signal_type: str = "",
        severity: str = "",
    ) -> TranslationResult:
        result = self._engine.translate(
            signal_id=signal_id,
            source_product=source_product,
            target_product=target_product,
            original_payload=original_payload,
            signal_type=signal_type,
            severity=severity,
        )
        if self._bus is not None:
            await self._emit(result)
        return result

    async def _emit(self, result: TranslationResult) -> None:
        from dataclasses import dataclass

        @dataclass
        class SignalTranslatedEvent(CorpusEvent):
            event_type: str = CorpusEventType.SIGNAL_TRANSLATED
            signal_id: str = ""
            source_product: str = ""
            target_product: str = ""
            method: str = ""
            confidence: float = 0.0

        await self._bus.publish(
            SignalTranslatedEvent(
                signal_id=result.signal_id,
                source_product=result.source_product,
                target_product=result.target_product,
                method=result.method,
                confidence=result.confidence,
            )
        )
