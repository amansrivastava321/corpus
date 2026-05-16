import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DecisionType(str, Enum):
    ALLOW = "ALLOW"       # proceed normally
    WARN = "WARN"         # proceed with logged caution
    DELAY = "DELAY"       # pause for delay_seconds and re-evaluate
    BLOCK = "BLOCK"       # hard stop — do not proceed
    ESCALATE = "ESCALATE" # raise to human oversight or governance layer
    REROUTE = "REROUTE"   # redirect the operation to reroute_target


class DecisionAuthority(str, Enum):
    CORPUS = "CORPUS"               # automated decision by the Corpus runtime
    POLICY_ENGINE = "POLICY_ENGINE" # decided by the governance policy engine
    HUMAN = "HUMAN"                 # human approved/rejected via the oversight interface
    PRODUCT = "PRODUCT"             # the requesting product overrode the decision


class DecisionEvidence(BaseModel):
    """Supporting evidence that justified the clearance decision."""

    signal_ids: list[str] = Field(default_factory=list)
    episode_ids: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
    risk_score: float | None = None   # 0.0 (safe) – 1.0 (critical risk)
    confidence: float = 1.0           # decision confidence 0.0–1.0


class ClearanceDecision(BaseModel):
    """
    Corpus's authoritative answer to a Checkpoint.

    Every Checkpoint ultimately resolves to exactly one ClearanceDecision.
    Decisions are immutable once issued; a new Checkpoint must be raised
    to request a revised decision.
    """

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    checkpoint_id: str
    decision: DecisionType
    reason: str
    authority: DecisionAuthority = DecisionAuthority.CORPUS
    evidence: DecisionEvidence = Field(default_factory=DecisionEvidence)
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delay_seconds: int | None = None    # populated when decision == DELAY
    reroute_target: str | None = None   # product_id populated when decision == REROUTE
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason cannot be empty")
        return v.strip()

    def is_blocking(self) -> bool:
        return self.decision in (DecisionType.BLOCK, DecisionType.ESCALATE)

    def allows_continuation(self) -> bool:
        return self.decision in (DecisionType.ALLOW, DecisionType.WARN)

    def requires_action(self) -> bool:
        return self.decision in (
            DecisionType.DELAY,
            DecisionType.BLOCK,
            DecisionType.ESCALATE,
            DecisionType.REROUTE,
        )
