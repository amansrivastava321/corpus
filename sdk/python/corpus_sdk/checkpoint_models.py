"""SDK-native checkpoint and decision data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckpointInfo:
    """A checkpoint registered with the Corpus interrupt engine."""

    id: str
    product_id: str
    product_name: str
    checkpoint_type: str
    status: str
    timeout_policy: str
    context: dict[str, Any]
    created_at: str
    updated_at: str
    resolved_at: str | None
    timeout_at: str | None
    decision_id: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointInfo":
        return cls(
            id=data["id"],
            product_id=data["product_id"],
            product_name=data["product_name"],
            checkpoint_type=data["checkpoint_type"],
            status=data["status"],
            timeout_policy=data["timeout_policy"],
            context=data.get("context", {}),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            resolved_at=data.get("resolved_at"),
            timeout_at=data.get("timeout_at"),
            decision_id=data.get("decision_id"),
        )

    @property
    def is_cleared(self) -> bool:
        return self.status in ("CLEARED", "RESOLVED")

    @property
    def is_blocked(self) -> bool:
        return self.status in ("BLOCKED", "ESCALATED")

    @property
    def is_terminal(self) -> bool:
        return self.status in ("RESOLVED", "CANCELLED", "EXPIRED")

    @property
    def is_waiting(self) -> bool:
        return self.status == "WAITING_CLEARANCE"


@dataclass
class DecisionInfo:
    """A clearance decision returned by the Corpus clearance engine."""

    id: str
    checkpoint_id: str
    decision_type: str
    reason: str
    decided_by: str
    trigger_signal_id: str | None
    created_at: str
    is_blocking: bool
    allows_continuation: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionInfo":
        return cls(
            id=data["id"],
            checkpoint_id=data["checkpoint_id"],
            decision_type=data["decision_type"],
            reason=data["reason"],
            decided_by=data.get("decided_by", "clearance_engine"),
            trigger_signal_id=data.get("trigger_signal_id"),
            created_at=data["created_at"],
            is_blocking=data.get("is_blocking", False),
            allows_continuation=data.get("allows_continuation", True),
            metadata=data.get("metadata", {}),
        )
