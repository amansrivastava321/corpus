"""RiskContext — contextual factors that modulate a signal's effective gravity."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskContext:
    """Contextual factors used by GravityEngine to adjust a signal's score."""

    # Whether the target product has an active WAITING_CLEARANCE checkpoint
    has_active_checkpoint: bool = False

    # Whether the target product is currently online (WebSocket connected)
    target_online: bool = True

    # Historical blocking count for this (source, target) pair in recent episodes
    historical_block_count: int = 0

    # Confidence override from the signal payload (0.0–1.0); None = use rule default
    signal_confidence: float | None = None

    # Trust level of the source product (0.0–1.0; higher = more trustworthy)
    source_trust: float = 0.8

    # Number of signals already in the pending queue for this target
    queue_depth: int = 0

    # Additional free-form evidence tags for the GravityScore
    extra_evidence: list[str] = field(default_factory=list)

    def score_multiplier(self) -> float:
        """Multiplicative adjustment factor based on context."""
        mult = 1.0
        if self.has_active_checkpoint:
            mult *= 1.3
        if not self.target_online:
            mult *= 0.7
        if self.historical_block_count > 3:
            mult *= 1.2
        if self.queue_depth > 10:
            mult *= 1.1
        mult *= self.source_trust
        return mult
