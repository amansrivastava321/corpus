"""Corpus internal event definitions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class CorpusEventType(str, Enum):
    PRODUCT_REGISTERED = "PRODUCT_REGISTERED"
    PRODUCT_HEARTBEAT = "PRODUCT_HEARTBEAT"
    PRODUCT_UNREGISTERED = "PRODUCT_UNREGISTERED"
    PRODUCT_STALE = "PRODUCT_STALE"
    PRODUCT_CONNECTED = "PRODUCT_CONNECTED"
    PRODUCT_DISCONNECTED = "PRODUCT_DISCONNECTED"
    SIGNAL_EMITTED = "SIGNAL_EMITTED"
    SIGNAL_ACKNOWLEDGED = "SIGNAL_ACKNOWLEDGED"
    SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
    SIGNAL_ROUTED = "SIGNAL_ROUTED"
    SIGNAL_DELIVERED = "SIGNAL_DELIVERED"
    HEARTBEAT_RECEIVED = "HEARTBEAT_RECEIVED"
    CHECKPOINT_REGISTERED = "CHECKPOINT_REGISTERED"
    CLEARANCE_REQUESTED = "CLEARANCE_REQUESTED"
    CLEARANCE_GRANTED = "CLEARANCE_GRANTED"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    EXECUTION_RESUMED = "EXECUTION_RESUMED"
    EXECUTION_ESCALATED = "EXECUTION_ESCALATED"
    CHECKPOINT_TIMEOUT = "CHECKPOINT_TIMEOUT"
    # Phase 5 — Gravity
    GRAVITY_COMPUTED = "GRAVITY_COMPUTED"
    # Phase 6 — Translation
    SIGNAL_TRANSLATED = "SIGNAL_TRANSLATED"
    # Phase 7 — Memory
    EPISODE_CREATED = "EPISODE_CREATED"
    EPISODE_UPDATED = "EPISODE_UPDATED"
    PATTERN_MINED = "PATTERN_MINED"
    # Phase 8 — Policy
    POLICY_LOADED = "POLICY_LOADED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    GOVERNANCE_ACTION_AUTHORIZED = "GOVERNANCE_ACTION_AUTHORIZED"
    GOVERNANCE_ACTION_DENIED = "GOVERNANCE_ACTION_DENIED"
    # Phase 9 — Orchestration
    WORKFLOW_CREATED = "WORKFLOW_CREATED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    # Phase 10 — Guardian
    GUARDIAN_INTERVENTION = "GUARDIAN_INTERVENTION"
    GUARDIAN_AUDIT_REQUESTED = "GUARDIAN_AUDIT_REQUESTED"


@dataclass
class CorpusEvent:
    event_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ProductRegisteredEvent(CorpusEvent):
    event_type: str = CorpusEventType.PRODUCT_REGISTERED
    product_id: str = ""
    product_name: str = ""


@dataclass
class ProductHeartbeatEvent(CorpusEvent):
    event_type: str = CorpusEventType.PRODUCT_HEARTBEAT
    product_id: str = ""
    status: str = "ACTIVE"


@dataclass
class ProductUnregisteredEvent(CorpusEvent):
    event_type: str = CorpusEventType.PRODUCT_UNREGISTERED
    product_id: str = ""


@dataclass
class SignalEmittedEvent(CorpusEvent):
    event_type: str = CorpusEventType.SIGNAL_EMITTED
    signal_id: str = ""
    signal_type: str = ""
    severity: str = ""
    source_product: str = ""
    target_product: str | None = None
    broadcast: bool = False


@dataclass
class SignalAcknowledgedEvent(CorpusEvent):
    event_type: str = CorpusEventType.SIGNAL_ACKNOWLEDGED
    signal_id: str = ""
    product_id: str = ""


@dataclass
class SignalExpiredEvent(CorpusEvent):
    event_type: str = CorpusEventType.SIGNAL_EXPIRED
    signal_id: str = ""


@dataclass
class ProductConnectedEvent(CorpusEvent):
    event_type: str = CorpusEventType.PRODUCT_CONNECTED
    product_id: str = ""
    product_name: str = ""


@dataclass
class ProductDisconnectedEvent(CorpusEvent):
    event_type: str = CorpusEventType.PRODUCT_DISCONNECTED
    product_id: str = ""
    product_name: str = ""


@dataclass
class SignalDeliveredEvent(CorpusEvent):
    event_type: str = CorpusEventType.SIGNAL_DELIVERED
    signal_id: str = ""
    product_id: str = ""
    via: str = "websocket"


@dataclass
class HeartbeatReceivedEvent(CorpusEvent):
    event_type: str = CorpusEventType.HEARTBEAT_RECEIVED
    product_id: str = ""
    product_name: str = ""


@dataclass
class CheckpointRegisteredEvent(CorpusEvent):
    event_type: str = CorpusEventType.CHECKPOINT_REGISTERED
    checkpoint_id: str = ""
    product_id: str = ""
    checkpoint_type: str = ""


@dataclass
class ClearanceGrantedEvent(CorpusEvent):
    event_type: str = CorpusEventType.CLEARANCE_GRANTED
    checkpoint_id: str = ""
    product_id: str = ""
    decision_type: str = ""
    decision_id: str = ""


@dataclass
class ExecutionBlockedEvent(CorpusEvent):
    event_type: str = CorpusEventType.EXECUTION_BLOCKED
    checkpoint_id: str = ""
    product_id: str = ""
    reason: str = ""
    trigger_signal_id: str | None = None


@dataclass
class ExecutionResumedEvent(CorpusEvent):
    event_type: str = CorpusEventType.EXECUTION_RESUMED
    checkpoint_id: str = ""
    product_id: str = ""


@dataclass
class ExecutionEscalatedEvent(CorpusEvent):
    event_type: str = CorpusEventType.EXECUTION_ESCALATED
    checkpoint_id: str = ""
    product_id: str = ""
    reason: str = ""
