"""SignalPrioritizer — ranks a batch of signals by gravity score."""

from __future__ import annotations

from corpus.gravity.gravity_engine import GravityEngine
from corpus.gravity.gravity_score import GravityScore
from corpus.gravity.risk_context import RiskContext
from corpus.schemas import Signal


class SignalPrioritizer:
    """Sorts multiple signals by their computed gravity (descending)."""

    def __init__(self, engine: GravityEngine | None = None) -> None:
        self._engine = engine or GravityEngine()

    def rank(
        self,
        signals: list[Signal],
        context: RiskContext | None = None,
    ) -> list[tuple[Signal, GravityScore]]:
        scored = [(s, self._engine.evaluate(s, context)) for s in signals]
        scored.sort(key=lambda pair: pair[1].score, reverse=True)
        return scored

    def top(
        self,
        signals: list[Signal],
        n: int = 1,
        context: RiskContext | None = None,
    ) -> list[tuple[Signal, GravityScore]]:
        return self.rank(signals, context)[:n]
