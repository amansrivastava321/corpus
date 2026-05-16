"""
Interrupt rules — maps active signals to clearance decisions.

Rules are evaluated in priority order.  The first matching rule wins.
Rules are configurable and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

from corpus.checkpoints.models import RuntimeDecisionType
from corpus.schemas.signal import Signal, SignalSeverity, SignalType


@dataclass
class RuleMatch:
    decision_type: RuntimeDecisionType
    reason: str
    trigger_signal_id: str


# Priority-ordered rules: (signal_type, min_severity) → decision
_RULES: list[tuple[SignalType, SignalSeverity, RuntimeDecisionType, str]] = [
    # BLOCK signals always block execution
    (SignalType.BLOCK, SignalSeverity.CRITICAL, RuntimeDecisionType.BLOCK,
     "Critical BLOCK signal active — execution halted"),
    (SignalType.BLOCK, SignalSeverity.HIGH, RuntimeDecisionType.BLOCK,
     "HIGH BLOCK signal active — execution halted"),
    (SignalType.BLOCK, SignalSeverity.MEDIUM, RuntimeDecisionType.BLOCK,
     "BLOCK signal active — execution halted"),
    (SignalType.BLOCK, SignalSeverity.LOW, RuntimeDecisionType.BLOCK,
     "BLOCK signal active — execution halted"),
    # ESCALATE signals escalate to human oversight
    (SignalType.ESCALATE, SignalSeverity.CRITICAL, RuntimeDecisionType.ESCALATE,
     "Critical ESCALATE signal active — human oversight required"),
    (SignalType.ESCALATE, SignalSeverity.HIGH, RuntimeDecisionType.ESCALATE,
     "ESCALATE signal active — human oversight required"),
    # INTERRUPT (CRITICAL) → block
    (SignalType.INTERRUPT, SignalSeverity.CRITICAL, RuntimeDecisionType.BLOCK,
     "Critical INTERRUPT signal — halting execution"),
    # INTERRUPT (HIGH/MEDIUM) → delay
    (SignalType.INTERRUPT, SignalSeverity.HIGH, RuntimeDecisionType.DELAY,
     "HIGH INTERRUPT signal — delaying execution"),
    (SignalType.INTERRUPT, SignalSeverity.MEDIUM, RuntimeDecisionType.DELAY,
     "INTERRUPT signal — delaying execution"),
]

# Severity priority for deduplication
_SEVERITY_ORDER = {
    SignalSeverity.CRITICAL: 0,
    SignalSeverity.HIGH: 1,
    SignalSeverity.MEDIUM: 2,
    SignalSeverity.LOW: 3,
}


class InterruptRules:
    """
    Stateless rule evaluator.

    Given a list of active blocking signals for a product, returns the
    most severe matching rule, or None (→ ALLOW) if no rules match.
    """

    def apply(self, signals: list[Signal]) -> RuleMatch | None:
        """Evaluate rules against active signals.  Returns the first match or None."""
        for sig_type, min_severity, decision_type, reason in _RULES:
            for signal in signals:
                if signal.type == sig_type:
                    if _SEVERITY_ORDER[signal.severity] <= _SEVERITY_ORDER[min_severity]:
                        return RuleMatch(
                            decision_type=decision_type,
                            reason=f"{reason} (signal: {signal.id[:8]}…)",
                            trigger_signal_id=signal.id,
                        )
        return None

    def describe(self) -> list[dict]:
        """Return human-readable rule descriptions for debugging."""
        return [
            {
                "signal_type": t.value,
                "min_severity": s.value,
                "decision": d.value,
                "reason": r,
            }
            for t, s, d, r in _RULES
        ]
