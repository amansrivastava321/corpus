import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EpisodeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    ARCHIVED = "ARCHIVED"


class EpisodeEventType(str, Enum):
    SIGNAL_RECEIVED = "SIGNAL_RECEIVED"
    INTERRUPT_TRIGGERED = "INTERRUPT_TRIGGERED"
    DECISION_MADE = "DECISION_MADE"
    CHECKPOINT_CLEARED = "CHECKPOINT_CLEARED"
    CHECKPOINT_BLOCKED = "CHECKPOINT_BLOCKED"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class EpisodeEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EpisodeEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    product_id: str | None = None
    signal_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Episode(BaseModel):
    """
    An episode groups all signals, events, and decisions that form a coherent
    interaction narrative between products — e.g. a security audit triggered by
    Inspectra that paused an Anvil execution.
    """

    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str | None = None
    status: EpisodeStatus = EpisodeStatus.ACTIVE
    signal_ids: list[str] = Field(default_factory=list)
    products_involved: list[str] = Field(default_factory=list)
    events: list[EpisodeEvent] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    outcome: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_event(self, event: EpisodeEvent) -> None:
        self.events.append(event)
        if event.signal_id and event.signal_id not in self.signal_ids:
            self.signal_ids.append(event.signal_id)
        if event.product_id and event.product_id not in self.products_involved:
            self.products_involved.append(event.product_id)

    def resolve(self, outcome: str) -> None:
        self.status = EpisodeStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)
        self.outcome = outcome

    def escalate(self) -> None:
        self.status = EpisodeStatus.ESCALATED

    def duration_seconds(self) -> float | None:
        if self.resolved_at is None:
            return None
        return (self.resolved_at - self.started_at).total_seconds()
