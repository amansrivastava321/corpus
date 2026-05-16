"""Background task that detects stale WebSocket connections.

Heartbeat flow:
  Client ──HEARTBEAT──► Corpus (update last_seen)
  If last_seen > stale_threshold:  ONLINE → STALE
  If last_seen > offline_threshold: STALE → OFFLINE
"""

from __future__ import annotations

import asyncio

from corpus import log
from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEventType, ProductDisconnectedEvent
from corpus.websocket.connection_manager import ConnectionManager
from corpus.websocket.presence_tracker import PresenceStatus, PresenceTracker

_log = log.get_logger("corpus.heartbeat_monitor")


class HeartbeatMonitor:
    """
    Runs as an asyncio background task.  Every `check_interval` seconds it
    inspects all ONLINE products and downgrades presence for ones that missed
    their heartbeat.

    Stale threshold:   ONLINE → STALE
    Offline threshold: STALE  → OFFLINE + disconnect
    """

    def __init__(
        self,
        presence_tracker: PresenceTracker,
        connection_manager: ConnectionManager,
        event_bus: EventBus,
        stale_threshold: int = 30,
        offline_threshold: int = 60,
        check_interval: int = 10,
    ) -> None:
        self._presence = presence_tracker
        self._conn_mgr = connection_manager
        self._bus = event_bus
        self._stale_threshold = stale_threshold
        self._offline_threshold = offline_threshold
        self._check_interval = check_interval
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="corpus-heartbeat-monitor")
            _log.info("heartbeat_monitor.started", interval=self._check_interval)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _log.info("heartbeat_monitor.stopped")

    async def record_heartbeat(self, product_id: str) -> None:
        self._presence.update_heartbeat(product_id)

    async def check_stale(self) -> list[str]:
        """Run one stale-detection pass. Returns list of product_ids that changed state."""
        changed: list[str] = []
        for presence in self._presence.get_all():
            if presence.status == PresenceStatus.OFFLINE:
                continue
            age = presence.seconds_since_seen()
            if age is None:
                continue

            if age > self._offline_threshold and presence.status == PresenceStatus.STALE:
                self._presence.mark_offline(presence.product_id)
                await self._conn_mgr.disconnect(presence.product_id)
                await self._bus.publish(
                    ProductDisconnectedEvent(
                        product_id=presence.product_id,
                        product_name=presence.product_name,
                    )
                )
                _log.warning(
                    "heartbeat_monitor.product_offline",
                    product_id=presence.product_id,
                    age_seconds=age,
                )
                changed.append(presence.product_id)

            elif age > self._stale_threshold and presence.status == PresenceStatus.ONLINE:
                self._presence.mark_stale(presence.product_id)
                _log.warning(
                    "heartbeat_monitor.product_stale",
                    product_id=presence.product_id,
                    age_seconds=age,
                )
                changed.append(presence.product_id)

        return changed

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._check_interval)
                await self.check_stale()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _log.error("heartbeat_monitor.error", error=str(exc))
