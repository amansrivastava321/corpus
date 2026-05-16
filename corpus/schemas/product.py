import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProductStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class ProductCapability(str, Enum):
    EMIT_SIGNALS = "EMIT_SIGNALS"
    RECEIVE_SIGNALS = "RECEIVE_SIGNALS"
    INTERRUPT = "INTERRUPT"           # can issue interrupts to other products
    BE_INTERRUPTED = "BE_INTERRUPTED" # can receive and honour interrupts
    AUDIT = "AUDIT"                   # can perform audits on request
    VALIDATE = "VALIDATE"             # can validate artifacts on request
    LEARN = "LEARN"                   # can share/consume learned patterns
    ORCHESTRATE = "ORCHESTRATE"       # can coordinate multi-product workflows


class ProductRegistration(BaseModel):
    product_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str
    description: str | None = None
    capabilities: list[ProductCapability] = Field(default_factory=list)
    endpoint: str | None = None            # HTTP base URL for REST callbacks
    websocket_endpoint: str | None = None  # WS endpoint for real-time delivery
    heartbeat_interval: int = 30           # seconds between heartbeats
    status: ProductStatus = ProductStatus.ACTIVE
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    def has_capability(self, cap: ProductCapability) -> bool:
        return cap in self.capabilities

    def mark_seen(self) -> None:
        self.last_seen = datetime.now(timezone.utc)

    def is_stale(self, tolerance_multiplier: float = 3.0) -> bool:
        """True if the product has missed more than tolerance_multiplier heartbeat cycles."""
        if self.last_seen is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_seen).total_seconds()
        return elapsed > self.heartbeat_interval * tolerance_multiplier


class ProductHeartbeat(BaseModel):
    product_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ProductStatus = ProductStatus.ACTIVE
    metrics: dict[str, Any] = Field(default_factory=dict)
