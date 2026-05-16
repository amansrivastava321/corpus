"""AuthorityResolver — decides which product has authority over an action."""

from __future__ import annotations

from corpus.policy.policy_models import GovernanceMode
from corpus.policy.trust_registry import TrustRegistry


class AuthorityResolver:
    """
    Resolves whether a source product has authority to perform an action
    (block/interrupt/escalate) on a target product, given current mode and trust.
    """

    def __init__(self, trust_registry: TrustRegistry, mode: GovernanceMode) -> None:
        self._trust = trust_registry
        self._mode = mode

    def can_block(self, source: str, target: str) -> bool:
        if self._mode == GovernanceMode.OBSERVER:
            return False
        return self._trust.numeric(source) >= 0.5

    def can_interrupt(self, source: str, target: str) -> bool:
        if self._mode == GovernanceMode.OBSERVER:
            return False
        return self._trust.numeric(source) >= 0.25

    def can_escalate(self, source: str, target: str) -> bool:
        return self._trust.numeric(source) >= 0.25

    def can_emit(self, source: str, signal_type: str) -> bool:
        """Any MEDIUM+ trusted product can emit all signal types."""
        numeric = self._trust.numeric(source)
        if signal_type in ("BLOCK", "ESCALATE"):
            return numeric >= 0.50
        if signal_type == "INTERRUPT":
            return numeric >= 0.25
        return True
