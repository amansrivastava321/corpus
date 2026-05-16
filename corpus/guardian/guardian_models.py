"""Guardian data models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class GuardianMode(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"  # record only, no action
    ADVISOR = "ADVISOR"           # warn + delay, no hard block
    GUARDIAN = "GUARDIAN"         # full intervention capability


class InterventionAction(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    WARN = "WARN"
    REQUEST_AUDIT = "REQUEST_AUDIT"
    DELAY = "DELAY"
    BLOCK = "BLOCK"
    REROUTE = "REROUTE"
    ESCALATE = "ESCALATE"


@dataclass
class RiskPrediction:
    risk_level: str         # LOW | MEDIUM | HIGH | CRITICAL
    risk_score: float       # 0.0–1.0
    risk_factors: list[str] = field(default_factory=list)
    memory_matches: int = 0
    predicted_action: InterventionAction = InterventionAction.OBSERVE_ONLY
    explanation: str = ""


@dataclass
class GuardianIntervention:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = ""
    signal_type: str = ""
    source_product: str = ""
    target_product: str = ""
    action: InterventionAction = InterventionAction.OBSERVE_ONLY
    reason: str = ""
    risk_score: float = 0.0
    approved_by_policy: bool = True
    dry_run: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source_product": self.source_product,
            "target_product": self.target_product,
            "action": self.action.value,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "approved_by_policy": self.approved_by_policy,
            "dry_run": self.dry_run,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GuardianIntervention":
        obj = cls(**{k: v for k, v in d.items() if k not in ("action",)})
        obj.action = InterventionAction(d["action"])
        return obj
