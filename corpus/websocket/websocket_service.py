"""
WebSocketService — orchestrates connection lifecycle, presence, and realtime dispatch.

No business logic lives inside the raw WebSocket route handler.  All decisions
are made here and the route just calls into this service.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from corpus import log
from corpus.errors import ProductNotFoundError, SignalAcknowledgementError, SignalNotFoundError
from corpus.events.event_bus import EventBus
from corpus.events.event_types import (
    CorpusEventType,
    HeartbeatReceivedEvent,
    ProductConnectedEvent,
    ProductDisconnectedEvent,
    SignalEmittedEvent,
)
from corpus.storage.repositories import DeliveryRepository, SignalRepository
from corpus.websocket.connection_manager import ConnectionManager
from corpus.websocket.heartbeat_monitor import HeartbeatMonitor
from corpus.websocket.message_types import (
    AckMessage,
    ConnectedMessage,
    ErrorMessage,
    HeartbeatAckMessage,
    PresenceUpdateMessage,
    WsMessageType,
    parse_client_message,
)
from corpus.websocket.presence_tracker import PresenceStatus, PresenceTracker
from corpus.websocket.realtime_dispatcher import RealtimeDispatcher

if TYPE_CHECKING:
    from corpus.services.signal_service import SignalService
    from starlette.websockets import WebSocket

_log = log.get_logger("corpus.websocket_service")


class WebSocketService:
    """
    Manages the full WebSocket lifecycle for a Corpus runtime.

    Responsibilities:
    - accept / reject connection attempts
    - drive presence transitions (ONLINE / OFFLINE / STALE)
    - flush queued signals on reconnect
    - route incoming ACK / HEARTBEAT messages
    - trigger realtime dispatch on SIGNAL_EMITTED events
    - broadcast presence changes to all connected products
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        presence_tracker: PresenceTracker,
        dispatcher: RealtimeDispatcher,
        heartbeat_monitor: HeartbeatMonitor,
        signal_repo: SignalRepository,
        delivery_repo: DeliveryRepository,
        event_bus: EventBus,
    ) -> None:
        self._cm = connection_manager
        self._presence = presence_tracker
        self._dispatcher = dispatcher
        self._monitor = heartbeat_monitor
        self._signal_repo = signal_repo
        self._delivery_repo = delivery_repo
        self._bus = event_bus

        # Subscribe to signal-emitted events for realtime dispatch
        self._bus.subscribe(CorpusEventType.SIGNAL_EMITTED, self._on_signal_emitted)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def handle_connect(
        self,
        product_id: str,
        product_name: str,
        websocket: Any,
        signal_service: "SignalService",
    ) -> None:
        """Called once the WebSocket upgrade is complete."""
        await self._cm.connect(product_id, websocket)
        presence = self._presence.mark_online(product_id, product_name)

        # Count how many signals are waiting
        pending = await self._signal_repo.get_pending_for_product(product_id)
        pending_count = len(pending)

        await websocket.send_json(
            ConnectedMessage(
                product_id=product_id,
                product_name=product_name,
                pending_count=pending_count,
            ).model_dump()
        )

        await self._bus.publish(
            ProductConnectedEvent(product_id=product_id, product_name=product_name)
        )

        # Broadcast presence update to all other connected products
        await self._cm.broadcast(
            PresenceUpdateMessage(
                product_id=product_id,
                product_name=product_name,
                status=PresenceStatus.ONLINE.value,
            ),
            exclude_product_id=product_id,
        )

        # Flush any pending signals immediately
        flushed = await self._dispatcher.flush_pending(product_id)

        _log.info(
            "ws.product_connected",
            product_id=product_id,
            product_name=product_name,
            pending_flushed=flushed,
        )

    async def handle_disconnect(self, product_id: str, product_name: str) -> None:
        """Called when a WebSocket connection closes (normally or on error)."""
        # Mark offline first (synchronous) before any await that could be cancelled
        self._presence.mark_offline(product_id)
        await self._cm.disconnect(product_id)

        await self._bus.publish(
            ProductDisconnectedEvent(product_id=product_id, product_name=product_name)
        )

        # Broadcast presence update
        await self._cm.broadcast(
            PresenceUpdateMessage(
                product_id=product_id,
                product_name=product_name,
                status=PresenceStatus.OFFLINE.value,
            )
        )

        _log.info("ws.product_disconnected", product_id=product_id)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        product_id: str,
        product_name: str,
        data: dict[str, Any],
        signal_service: "SignalService",
    ) -> None:
        """Dispatch an incoming client message to the appropriate handler."""
        msg = parse_client_message(data)
        if msg.message_type == WsMessageType.HEARTBEAT:
            await self._handle_heartbeat(product_id, product_name)
        elif msg.message_type == WsMessageType.ACK:
            await self._handle_ack(product_id, msg, signal_service)  # type: ignore[arg-type]
        else:
            _log.debug("ws.unknown_message_type", type=data.get("message_type"))

    async def _handle_heartbeat(self, product_id: str, product_name: str) -> None:
        await self._monitor.record_heartbeat(product_id)
        await self._bus.publish(
            HeartbeatReceivedEvent(product_id=product_id, product_name=product_name)
        )
        ws = self._cm.get_connection(product_id)
        if ws:
            ack = HeartbeatAckMessage(
                server_time=datetime.now(timezone.utc).isoformat()
            )
            await ws.send_json(ack.model_dump())

    async def _handle_ack(
        self,
        product_id: str,
        msg: AckMessage,
        signal_service: "SignalService",
    ) -> None:
        ws = self._cm.get_connection(product_id)
        try:
            await signal_service.acknowledge(msg.signal_id, product_id)
            _log.info("ws.signal_acked", signal_id=msg.signal_id, product_id=product_id)
        except (SignalNotFoundError, SignalAcknowledgementError) as exc:
            if ws:
                await ws.send_json(
                    ErrorMessage(code="ack_error", detail=str(exc)).model_dump()
                )

    # ------------------------------------------------------------------
    # Realtime dispatch (triggered by EventBus)
    # ------------------------------------------------------------------

    async def _on_signal_emitted(self, event: SignalEmittedEvent) -> None:
        """Push a freshly emitted signal to any connected targets."""
        signal = await self._signal_repo.get(event.signal_id)
        if signal is None:
            return

        # Delivery records were created by the router; read them to find targets
        target_ids = await self._delivery_repo.get_delivery_targets(event.signal_id)
        if not target_ids:
            return

        await self._dispatcher.dispatch_to_targets(signal, target_ids)

    # ------------------------------------------------------------------
    # Presence queries
    # ------------------------------------------------------------------

    def get_presence(self, product_id: str) -> dict | None:
        p = self._presence.get(product_id)
        return p.to_dict() if p else None

    def list_presence(self) -> list[dict]:
        return [p.to_dict() for p in self._presence.get_all()]
