import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class SignalSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SignalType(str, Enum):
    INFORM = "INFORM"         # passive notification, no response required
    CONSULT = "CONSULT"       # request for advice/input, response expected
    INTERRUPT = "INTERRUPT"   # request to pause the current operation
    BLOCK = "BLOCK"           # hard stop — cannot proceed without clearance
    VALIDATE = "VALIDATE"     # request audit or validation of an artifact
    LEARN = "LEARN"           # share learned patterns or insights
    ESCALATE = "ESCALATE"     # escalate to a higher authority or human oversight


class SignalStatus(str, Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class SignalMetadata(BaseModel):
    tags: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    requires_ack: bool = False
    broadcast: bool = False


class Signal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: SignalType
    severity: SignalSeverity
    source_product: str
    target_product: str | None = None  # None = broadcast
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: SignalMetadata = Field(default_factory=SignalMetadata)
    status: SignalStatus = SignalStatus.PENDING
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None   # links related signals in a session
    parent_signal_id: str | None = None  # for chained signal trees
    ttl: int | None = None              # seconds until expiry; None = never

    @field_validator("source_product")
    @classmethod
    def source_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_product cannot be empty")
        return v.strip()

    @model_validator(mode="after")
    def broadcast_target_consistency(self) -> "Signal":
        if self.metadata.broadcast and self.target_product is not None:
            raise ValueError("broadcast signals cannot specify a target_product")
        return self

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return elapsed > self.ttl

    def requires_interrupt(self) -> bool:
        return self.type in (SignalType.INTERRUPT, SignalType.BLOCK)

    def gravity_weight(self) -> float:
        """Combined severity × type weight used by the gravity engine for prioritization."""
        severity_weights = {
            SignalSeverity.LOW: 1.0,
            SignalSeverity.MEDIUM: 2.5,
            SignalSeverity.HIGH: 5.0,
            SignalSeverity.CRITICAL: 10.0,
        }
        type_multipliers = {
            SignalType.INFORM: 0.5,
            SignalType.LEARN: 0.7,
            SignalType.CONSULT: 1.0,
            SignalType.VALIDATE: 1.5,
            SignalType.INTERRUPT: 2.0,
            SignalType.ESCALATE: 2.5,
            SignalType.BLOCK: 3.0,
        }
        return severity_weights[self.severity] * type_multipliers[self.type]
