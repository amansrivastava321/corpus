"""Policy models — rules, trust levels, modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GovernanceMode(str, Enum):
    OBSERVER = "OBSERVER"   # record only — no interventions
    ADVISOR = "ADVISOR"     # warn/delay but no hard block
    GUARDIAN = "GUARDIAN"   # can block, reroute, escalate


class TrustLevel(str, Enum):
    UNTRUSTED = "UNTRUSTED"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    TRUSTED = "TRUSTED"

    def numeric(self) -> float:
        return {
            TrustLevel.UNTRUSTED: 0.0,
            TrustLevel.LOW: 0.25,
            TrustLevel.MEDIUM: 0.50,
            TrustLevel.HIGH: 0.75,
            TrustLevel.TRUSTED: 1.0,
        }[self]


@dataclass
class PolicyRule:
    """A single policy rule controlling who can do what to whom."""
    name: str
    source_product: str | None       # None = match any
    target_product: str | None       # None = match any
    allowed_signal_types: list[str]  # empty = allow all
    min_trust_level: TrustLevel = TrustLevel.LOW
    max_severity: str | None = None  # block signals above this severity
    requires_mode: GovernanceMode = GovernanceMode.OBSERVER
    description: str = ""


@dataclass
class PolicyEvaluationResult:
    authorized: bool
    mode: GovernanceMode
    reason: str
    matched_rule: str | None = None
    action_taken: str = "ALLOW"  # ALLOW | WARN | DENY
    evidence: list[str] = field(default_factory=list)
