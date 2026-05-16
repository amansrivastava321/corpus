import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CheckpointType(str, Enum):
    PRE_ANALYSIS = "PRE_ANALYSIS"       # before a product starts analysing an artifact
    PRE_EXECUTION = "PRE_EXECUTION"     # before executing a plan or job
    PRE_COMMIT = "PRE_COMMIT"           # before committing code or state
    PRE_RELEASE = "PRE_RELEASE"         # before a release or deployment
    POST_EXECUTION = "POST_EXECUTION"   # after execution, before result is published
    CUSTOM = "CUSTOM"                   # product-defined checkpoint


class CheckpointStatus(str, Enum):
    PENDING = "PENDING"         # awaiting Corpus evaluation
    EVALUATING = "EVALUATING"   # Corpus is gathering signals and making a decision
    CLEARED = "CLEARED"         # safe to proceed
    BLOCKED = "BLOCKED"         # must not proceed
    DELAYED = "DELAYED"         # retry after delay_seconds
    EXPIRED = "EXPIRED"         # ttl elapsed before a decision was reached


class CheckpointContext(BaseModel):
    """Rich context supplied by the product to help Corpus make a clearance decision."""

    module: str | None = None
    file_paths: list[str] = Field(default_factory=list)
    operation: str | None = None
    risk_indicators: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class Checkpoint(BaseModel):
    """
    A synchronisation point where a product pauses and requests clearance
    from Corpus before proceeding with a potentially risky operation.
    """

    checkpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    checkpoint_type: CheckpointType
    product_id: str
    context: CheckpointContext = Field(default_factory=CheckpointContext)
    status: CheckpointStatus = CheckpointStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluated_at: datetime | None = None
    cleared_at: datetime | None = None
    expires_at: datetime | None = None
    blocking_signal_ids: list[str] = Field(default_factory=list)
    decision_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_terminal(self) -> bool:
        return self.status in (
            CheckpointStatus.CLEARED,
            CheckpointStatus.BLOCKED,
            CheckpointStatus.EXPIRED,
        )

    def wait_seconds(self) -> float:
        """Seconds this checkpoint has been pending."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()
