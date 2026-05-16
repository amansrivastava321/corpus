"""
Runtime checkpoint models for Phase 4 — the execution governance layer.

These extend the Phase 0 schema concepts with the full runtime lifecycle:
registration → awaiting clearance → decision → resolution.

The Phase 0 schemas (corpus.schemas.checkpoint / corpus.schemas.decision)
are used for JSON contract validation.  These models are the live runtime
entities persisted in SQLite and used throughout the clearance engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RuntimeCheckpointStatus(str, Enum):
    REGISTERED = "REGISTERED"              # just created, not yet awaiting clearance
    WAITING_CLEARANCE = "WAITING_CLEARANCE"  # product called request_clearance
    CLEARED = "CLEARED"                    # ALLOW or WARN decision — proceed
    BLOCKED = "BLOCKED"                    # BLOCK decision — halt execution
    DELAYED = "DELAYED"                    # DELAY decision — pause and retry
    REROUTED = "REROUTED"                  # REROUTE decision — switch path
    ESCALATED = "ESCALATED"               # ESCALATE decision — human involvement
    RESOLVED = "RESOLVED"                  # execution completed after clearance
    CANCELLED = "CANCELLED"               # product cancelled the checkpoint
    EXPIRED = "EXPIRED"                    # timeout elapsed before decision


class TimeoutPolicy(str, Enum):
    FAIL_OPEN = "FAIL_OPEN"        # ALLOW on timeout
    FAIL_CLOSED = "FAIL_CLOSED"    # BLOCK on timeout
    ESCALATE = "ESCALATE"          # ESCALATE on timeout


class RuntimeDecisionType(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    DELAY = "DELAY"
    BLOCK = "BLOCK"
    REROUTE = "REROUTE"
    ESCALATE = "ESCALATE"

    def is_blocking(self) -> bool:
        return self in (RuntimeDecisionType.BLOCK, RuntimeDecisionType.ESCALATE)

    def allows_continuation(self) -> bool:
        return self in (RuntimeDecisionType.ALLOW, RuntimeDecisionType.WARN)

    def to_checkpoint_status(self) -> RuntimeCheckpointStatus:
        return {
            RuntimeDecisionType.ALLOW: RuntimeCheckpointStatus.CLEARED,
            RuntimeDecisionType.WARN: RuntimeCheckpointStatus.CLEARED,
            RuntimeDecisionType.BLOCK: RuntimeCheckpointStatus.BLOCKED,
            RuntimeDecisionType.DELAY: RuntimeCheckpointStatus.DELAYED,
            RuntimeDecisionType.REROUTE: RuntimeCheckpointStatus.REROUTED,
            RuntimeDecisionType.ESCALATE: RuntimeCheckpointStatus.ESCALATED,
        }[self]


class RuntimeCheckpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    product_name: str
    checkpoint_type: str
    status: RuntimeCheckpointStatus = RuntimeCheckpointStatus.REGISTERED
    timeout_policy: TimeoutPolicy = TimeoutPolicy.FAIL_OPEN
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    timeout_at: datetime | None = None
    decision_id: str | None = None

    def is_expired(self) -> bool:
        if self.timeout_at is None:
            return False
        return datetime.now(timezone.utc) > self.timeout_at

    def is_terminal(self) -> bool:
        return self.status in (
            RuntimeCheckpointStatus.RESOLVED,
            RuntimeCheckpointStatus.CANCELLED,
            RuntimeCheckpointStatus.EXPIRED,
        )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def wait_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()


class RuntimeDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    checkpoint_id: str
    decision_type: RuntimeDecisionType
    reason: str
    decided_by: str = "clearance_engine"
    trigger_signal_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_blocking(self) -> bool:
        return self.decision_type.is_blocking()

    def allows_continuation(self) -> bool:
        return self.decision_type.allows_continuation()
