"""
ClearanceEngine — evaluates whether execution may proceed at a checkpoint.

Evaluation steps (in order):
  1. Check active BLOCK/INTERRUPT/ESCALATE signals for the product.
  2. Apply interrupt rules to those signals.
  3. If a rule matches → blocking/delay decision.
  4. If no rules match → ALLOW.

Decisions are deterministic and fully auditable.
"""

from __future__ import annotations

from corpus.checkpoints.models import RuntimeCheckpoint, RuntimeDecision, RuntimeDecisionType
from corpus.interrupts.interrupt_rules import InterruptRules
from corpus.storage.repositories import SignalRepository


class ClearanceEngine:
    """
    Synchronous evaluation of a checkpoint against active signals.

    The engine does NOT modify state — it returns a RuntimeDecision.
    Persistence and status transitions are the responsibility of CheckpointService.
    """

    def __init__(
        self,
        signal_repo: SignalRepository,
        interrupt_rules: InterruptRules | None = None,
    ) -> None:
        self._signal_repo = signal_repo
        self._rules = interrupt_rules or InterruptRules()

    async def evaluate(self, checkpoint: RuntimeCheckpoint) -> RuntimeDecision:
        """Evaluate a checkpoint and return the clearance decision."""
        # Fetch all unacknowledged blocking signals for this product
        blocking_signals = await self._signal_repo.get_blocking_signals_for_product(
            checkpoint.product_id
        )

        # Apply rules
        match = self._rules.apply(blocking_signals)

        if match is not None:
            return RuntimeDecision(
                checkpoint_id=checkpoint.id,
                decision_type=match.decision_type,
                reason=match.reason,
                decided_by="clearance_engine",
                trigger_signal_id=match.trigger_signal_id,
                metadata={
                    "checkpoint_type": checkpoint.checkpoint_type,
                    "signals_evaluated": len(blocking_signals),
                },
            )

        return RuntimeDecision(
            checkpoint_id=checkpoint.id,
            decision_type=RuntimeDecisionType.ALLOW,
            reason="No blocking signals detected — execution cleared",
            decided_by="clearance_engine",
            metadata={
                "checkpoint_type": checkpoint.checkpoint_type,
                "signals_evaluated": len(blocking_signals),
            },
        )
