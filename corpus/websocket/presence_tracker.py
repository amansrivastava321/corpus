"""Tracks which products are online, offline, stale, or reconnecting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class PresenceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    STALE = "STALE"
    RECONNECTING = "RECONNECTING"


@dataclass
class ProductPresence:
    product_id: str
    product_name: str
    status: PresenceStatus = PresenceStatus.OFFLINE
    connected: bool = False
    connected_at: datetime | None = None
    last_seen: datetime | None = None          # last heartbeat or connect
    disconnected_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "status": self.status.value,
            "connected": self.connected,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "disconnected_at": (
                self.disconnected_at.isoformat() if self.disconnected_at else None
            ),
        }

    def seconds_since_seen(self) -> float | None:
        if self.last_seen is None:
            return None
        return (datetime.now(timezone.utc) - self.last_seen).total_seconds()


class PresenceTracker:
    """
    In-memory presence state for all products that have ever connected via WebSocket.

    Presence is independent of signal routing — it only reflects WebSocket
    connectivity.  Products that only use the REST API will not appear here.
    """

    def __init__(self) -> None:
        self._presence: dict[str, ProductPresence] = {}

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def mark_online(self, product_id: str, product_name: str) -> ProductPresence:
        now = datetime.now(timezone.utc)
        p = self._presence.get(product_id)
        if p is None:
            p = ProductPresence(product_id=product_id, product_name=product_name)
            self._presence[product_id] = p
        p.status = PresenceStatus.ONLINE
        p.connected = True
        p.connected_at = now
        p.last_seen = now
        p.disconnected_at = None
        p.product_name = product_name
        return p

    def mark_offline(self, product_id: str) -> ProductPresence | None:
        p = self._presence.get(product_id)
        if p is None:
            return None
        p.status = PresenceStatus.OFFLINE
        p.connected = False
        p.disconnected_at = datetime.now(timezone.utc)
        return p

    def mark_stale(self, product_id: str) -> ProductPresence | None:
        p = self._presence.get(product_id)
        if p is None or p.status == PresenceStatus.OFFLINE:
            return None
        p.status = PresenceStatus.STALE
        return p

    def mark_reconnecting(self, product_id: str) -> ProductPresence | None:
        p = self._presence.get(product_id)
        if p is None:
            return None
        p.status = PresenceStatus.RECONNECTING
        p.connected = False
        return p

    def update_heartbeat(self, product_id: str) -> ProductPresence | None:
        p = self._presence.get(product_id)
        if p is None:
            return None
        p.last_seen = datetime.now(timezone.utc)
        if p.status in (PresenceStatus.STALE, PresenceStatus.RECONNECTING):
            p.status = PresenceStatus.ONLINE
        return p

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, product_id: str) -> ProductPresence | None:
        return self._presence.get(product_id)

    def get_all(self) -> list[ProductPresence]:
        return list(self._presence.values())

    def get_stale_products(self, threshold_seconds: int = 30) -> list[ProductPresence]:
        """Return ONLINE products that haven't sent a heartbeat within the threshold."""
        result = []
        for p in self._presence.values():
            if p.status != PresenceStatus.ONLINE:
                continue
            age = p.seconds_since_seen()
            if age is not None and age > threshold_seconds:
                result.append(p)
        return result

    def is_online(self, product_id: str) -> bool:
        p = self._presence.get(product_id)
        return p is not None and p.status == PresenceStatus.ONLINE
