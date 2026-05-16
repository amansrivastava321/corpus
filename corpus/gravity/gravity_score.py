"""GravityScore — the output of a gravity evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GravityAction(str, Enum):
    IGNORE = "IGNORE"
    QUEUE = "QUEUE"
    INFORM = "INFORM"
    WARN = "WARN"
    DELAY = "DELAY"
    BLOCK = "BLOCK"
    REROUTE = "REROUTE"
    ESCALATE = "ESCALATE"

    @property
    def is_blocking(self) -> bool:
        return self in (GravityAction.BLOCK, GravityAction.ESCALATE)

    @property
    def requires_checkpoint(self) -> bool:
        return self in (GravityAction.DELAY, GravityAction.BLOCK, GravityAction.REROUTE, GravityAction.ESCALATE)


@dataclass
class GravityScore:
    score: float
    action: GravityAction
    explanation: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    signal_id: str = ""
    computed_by: str = "gravity_engine"

    @property
    def is_blocking(self) -> bool:
        return self.action.is_blocking

    @property
    def requires_checkpoint(self) -> bool:
        return self.action.requires_checkpoint
