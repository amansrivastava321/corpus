"""RiskPredictor — scores incoming signals for proactive threat detection."""

from __future__ import annotations

from corpus.guardian.guardian_models import InterventionAction, RiskPrediction
from corpus.schemas import Signal, SignalSeverity, SignalType


_SEVERITY_SCORES = {
    SignalSeverity.LOW: 0.1,
    SignalSeverity.MEDIUM: 0.4,
    SignalSeverity.HIGH: 0.7,
    SignalSeverity.CRITICAL: 1.0,
}

_TYPE_MULTIPLIERS = {
    SignalType.INFORM: 0.2,
    SignalType.LEARN: 0.3,
    SignalType.CONSULT: 0.5,
    SignalType.VALIDATE: 0.7,
    SignalType.INTERRUPT: 0.8,
    SignalType.ESCALATE: 0.9,
    SignalType.BLOCK: 1.0,
}

_RISK_LEVELS = [
    (0.8, "CRITICAL"),
    (0.6, "HIGH"),
    (0.3, "MEDIUM"),
    (0.0, "LOW"),
]


class RiskPredictor:
    """
    Computes a risk prediction for a signal using:
    - signal type × severity → base score
    - memory match count → historical multiplier
    - gravity action → additional weight
    """

    def predict(
        self,
        signal: Signal,
        gravity_action: str = "ALLOW",
        memory_block_count: int = 0,
    ) -> RiskPrediction:
        base = _SEVERITY_SCORES[signal.severity] * _TYPE_MULTIPLIERS[signal.type]
        factors: list[str] = [
            f"type={signal.type.value}",
            f"severity={signal.severity.value}",
            f"base_score={base:.2f}",
        ]

        # Gravity modulation
        if gravity_action in ("BLOCK", "ESCALATE"):
            base = min(1.0, base * 1.5)
            factors.append(f"gravity={gravity_action}")
        elif gravity_action in ("DELAY", "WARN"):
            base = min(1.0, base * 1.2)
            factors.append(f"gravity={gravity_action}")

        # Memory-informed historical risk
        if memory_block_count > 0:
            boost = min(0.3, memory_block_count * 0.05)
            base = min(1.0, base + boost)
            factors.append(f"memory_blocks={memory_block_count}")

        # Determine level
        risk_level = "LOW"
        for threshold, level in _RISK_LEVELS:
            if base >= threshold:
                risk_level = level
                break

        # Predict action
        if base >= 0.8:
            predicted = InterventionAction.BLOCK
        elif base >= 0.6:
            predicted = InterventionAction.REQUEST_AUDIT
        elif base >= 0.4:
            predicted = InterventionAction.WARN
        elif base >= 0.2:
            predicted = InterventionAction.OBSERVE_ONLY
        else:
            predicted = InterventionAction.OBSERVE_ONLY

        return RiskPrediction(
            risk_level=risk_level,
            risk_score=round(base, 3),
            risk_factors=factors,
            memory_matches=memory_block_count,
            predicted_action=predicted,
            explanation=f"Risk={risk_level} ({base:.2f}) — predicted action: {predicted.value}",
        )
