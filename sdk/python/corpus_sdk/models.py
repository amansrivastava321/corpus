"""SDK-native models — independent of corpus.schemas.

These are intentionally minimal so products only need corpus-sdk-python installed,
not the full corpus server package.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProductInfo:
    product_id: str
    name: str
    version: str
    status: str
    capabilities: list[str]
    registered_at: str
    last_seen: str | None = None
    endpoint: str | None = None
    websocket_endpoint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "ProductInfo":
        return cls(
            product_id=d["product_id"],
            name=d["name"],
            version=d["version"],
            status=d["status"],
            capabilities=d.get("capabilities", []),
            registered_at=d["registered_at"],
            last_seen=d.get("last_seen"),
            endpoint=d.get("endpoint"),
            websocket_endpoint=d.get("websocket_endpoint"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class ReceivedSignal:
    """A signal received from the pending queue."""

    id: str
    signal_type: str
    severity: str
    source_product: str
    target_product: str | None
    payload: dict[str, Any]
    status: str
    timestamp: str
    broadcast: bool
    correlation_id: str | None = None
    parent_signal_id: str | None = None
    ttl: int | None = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ReceivedSignal":
        meta = d.get("metadata") or {}
        return cls(
            id=d["id"],
            signal_type=d["type"],
            severity=d["severity"],
            source_product=d["source_product"],
            target_product=d.get("target_product"),
            payload=d.get("payload") or {},
            status=d["status"],
            timestamp=d["timestamp"],
            broadcast=meta.get("broadcast", False),
            correlation_id=d.get("correlation_id"),
            parent_signal_id=d.get("parent_signal_id"),
            ttl=d.get("ttl"),
            tags=meta.get("tags", []),
        )


@dataclass
class EmittedSignal(ReceivedSignal):
    """Result returned after emitting a signal — same shape, different intent."""

    @classmethod
    def from_dict(cls, d: dict) -> "EmittedSignal":  # type: ignore[override]
        base = ReceivedSignal.from_dict(d)
        return cls(**base.__dict__)


@dataclass
class HealthInfo:
    status: str
    version: str
    products_registered: int
    pending_deliveries: int
    uptime_seconds: float
    total_signals_received: int
    started_at: str
    last_error: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "HealthInfo":
        return cls(
            status=d["status"],
            version=d["version"],
            products_registered=d["products_registered"],
            pending_deliveries=d["pending_deliveries"],
            uptime_seconds=d["uptime_seconds"],
            total_signals_received=d["total_signals_received"],
            started_at=d["started_at"],
            last_error=d.get("last_error"),
        )
