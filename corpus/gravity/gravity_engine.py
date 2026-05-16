"""GravityEngine — computes effective signal importance and recommended action."""

from __future__ import annotations

import logging

from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEvent, CorpusEventType
from corpus.gravity.gravity_rules import apply_rules
from corpus.gravity.gravity_score import GravityAction, GravityScore
from corpus.gravity.risk_context import RiskContext
from corpus.schemas import Signal

_log = logging.getLogger(__name__)


class GravityEngine:
    """
    Stateless gravity evaluator.

    Given a Signal and an optional RiskContext, computes:
    - effective gravity score (float)
    - recommended action (GravityAction)
    - explanation string
    - confidence (0.0–1.0)
    - evidence list (for auditability)
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus

    def evaluate(self, signal: Signal, context: RiskContext | None = None) -> GravityScore:
        ctx = context or RiskContext()
        base_weight = signal.gravity_weight()
        adjusted_weight = base_weight * ctx.score_multiplier()

        evidence: list[str] = []
        evidence.append(f"base_weight={base_weight:.2f}")
        evidence.append(f"context_multiplier={ctx.score_multiplier():.2f}")
        evidence.append(f"adjusted_weight={adjusted_weight:.2f}")
        evidence.extend(ctx.extra_evidence)

        # Rules match on base weight (signal characteristics), not context-adjusted weight.
        # Context only modulates the final score value.
        matched = apply_rules(signal.type, signal.severity, base_weight)

        if matched is not None:
            confidence = ctx.signal_confidence if ctx.signal_confidence is not None else matched.confidence
            score = GravityScore(
                score=adjusted_weight,
                action=matched.action,
                explanation=matched.explanation,
                confidence=confidence,
                evidence=evidence + [f"rule={matched.name}"],
                signal_id=signal.id,
            )
        else:
            # No rule matched — informational signal or very low weight
            action = GravityAction.QUEUE if adjusted_weight > 0.5 else GravityAction.IGNORE
            score = GravityScore(
                score=adjusted_weight,
                action=action,
                explanation="No gravity rule matched — low importance signal",
                confidence=0.6,
                evidence=evidence + ["rule=none"],
                signal_id=signal.id,
            )

        if self._bus is not None:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._emit_event(signal, score))
            except RuntimeError:
                pass

        _log.debug(
            "gravity_computed",
            extra={
                "signal_id": signal.id,
                "score": score.score,
                "action": score.action,
                "confidence": score.confidence,
            },
        )
        return score

    async def evaluate_async(self, signal: Signal, context: RiskContext | None = None) -> GravityScore:
        score = self.evaluate(signal, context)
        if self._bus is not None:
            await self._emit_event(signal, score)
        return score

    async def _emit_event(self, signal: Signal, score: GravityScore) -> None:
        event = GravityComputedEvent(
            signal_id=signal.id,
            signal_type=signal.type.value,
            severity=signal.severity.value,
            score=score.score,
            action=score.action.value,
            confidence=score.confidence,
        )
        await self._bus.publish(event)


from dataclasses import dataclass


@dataclass
class GravityComputedEvent(CorpusEvent):
    event_type: str = CorpusEventType.GRAVITY_COMPUTED
    signal_id: str = ""
    signal_type: str = ""
    severity: str = ""
    score: float = 0.0
    action: str = ""
    confidence: float = 0.0
