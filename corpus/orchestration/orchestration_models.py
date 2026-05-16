"""Orchestration data models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    RESPONDED = "RESPONDED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class SynthesisDecision(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"
    REROUTE = "REROUTE"
    ESCALATE = "ESCALATE"


@dataclass
class OrchestrationTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    target_product: str = ""
    capability_required: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 10.0
    status: TaskStatus = TaskStatus.PENDING
    dispatched_at: str | None = None
    response: dict[str, Any] | None = None
    responded_at: str | None = None
    signal_id: str | None = None  # signal emitted to dispatch this task

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "target_product": self.target_product,
            "capability_required": self.capability_required,
            "payload": self.payload,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "dispatched_at": self.dispatched_at,
            "response": self.response,
            "responded_at": self.responded_at,
            "signal_id": self.signal_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OrchestrationTask":
        t = cls(**{k: v for k, v in d.items() if k != "status"})
        t.status = TaskStatus(d["status"])
        return t


@dataclass
class SynthesizedDecision:
    decision: SynthesisDecision
    confidence: float
    reasoning: str
    contributing_factors: list[str] = field(default_factory=list)
    blocking_signals: int = 0
    warning_signals: int = 0
    timeout_tasks: int = 0

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "contributing_factors": self.contributing_factors,
            "blocking_signals": self.blocking_signals,
            "warning_signals": self.warning_signals,
            "timeout_tasks": self.timeout_tasks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SynthesizedDecision":
        return cls(
            decision=SynthesisDecision(d["decision"]),
            confidence=d["confidence"],
            reasoning=d["reasoning"],
            contributing_factors=d.get("contributing_factors", []),
            blocking_signals=d.get("blocking_signals", 0),
            warning_signals=d.get("warning_signals", 0),
            timeout_tasks=d.get("timeout_tasks", 0),
        )


@dataclass
class OrchestrationWorkflow:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    initiating_product: str = ""
    subject: dict[str, Any] = field(default_factory=dict)  # what is being orchestrated
    status: WorkflowStatus = WorkflowStatus.PENDING
    tasks: list[OrchestrationTask] = field(default_factory=list)
    synthesis: SynthesizedDecision | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "initiating_product": self.initiating_product,
            "subject": self.subject,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "synthesis": self.synthesis.to_dict() if self.synthesis else None,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OrchestrationWorkflow":
        wf = cls(
            id=d["id"],
            name=d["name"],
            initiating_product=d["initiating_product"],
            subject=d.get("subject", {}),
            status=WorkflowStatus(d["status"]),
            tasks=[OrchestrationTask.from_dict(t) for t in d.get("tasks", [])],
            synthesis=SynthesizedDecision.from_dict(d["synthesis"]) if d.get("synthesis") else None,
            created_at=d["created_at"],
            started_at=d.get("started_at"),
            completed_at=d.get("completed_at"),
            error=d.get("error"),
        )
        return wf
