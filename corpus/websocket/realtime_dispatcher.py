"""Pushes signals to connected products over WebSocket.

If the target is connected, the signal is sent immediately and the delivery
record is updated to DELIVERED.  If the target is offline the signal stays
PENDING in the persistence layer and can be retrieved via REST polling or
flushed on reconnect.
"""

from __future__ import annotations

from corpus import log
from corpus.events.event_bus import EventBus
from corpus.events.event_types import SignalDeliveredEvent
from corpus.schemas import Signal
from corpus.storage.repositories import DeliveryRepository, SignalRepository
from corpus.websocket.connection_manager import ConnectionManager
from corpus.websocket.message_types import SignalMessage

_log = log.get_logger("corpus.realtime_dispatcher")


class RealtimeDispatcher:
    """
    Delivers signals to connected products via WebSocket.

    Routing logic (which product_ids to target) is owned by the SignalRouter.
    This dispatcher only handles the WS push and delivery-status bookkeeping.
    It is called by WebSocketService after a signal is emitted.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        signal_repo: SignalRepository,
        delivery_repo: DeliveryRepository,
        event_bus: EventBus,
    ) -> None:
        self._cm = connection_manager
        self._signal_repo = signal_repo
        self._delivery_repo = delivery_repo
        self._bus = event_bus

    async def dispatch(self, signal: Signal, product_id: str) -> bool:
        """Push a single signal to one product. Returns True if delivered."""
        if not self._cm.is_connected(product_id):
            return False
        msg = SignalMessage(signal=signal.model_dump(mode="json"))
        delivered = await self._cm.send_message(product_id, msg)
        if delivered:
            await self._delivery_repo.mark_delivered(signal.id, product_id)
            await self._bus.publish(
                SignalDeliveredEvent(signal_id=signal.id, product_id=product_id)
            )
            _log.info(
                "signal.delivered_realtime",
                signal_id=signal.id,
                product_id=product_id,
                signal_type=signal.type.value,
            )
        else:
            await self._delivery_repo.mark_failed(signal.id, product_id)
            _log.warning(
                "signal.delivery_failed",
                signal_id=signal.id,
                product_id=product_id,
            )
        return delivered

    async def dispatch_to_targets(
        self, signal: Signal, target_product_ids: list[str]
    ) -> int:
        """Dispatch to a list of product_ids. Returns count of successful deliveries."""
        count = 0
        for pid in target_product_ids:
            if await self.dispatch(signal, pid):
                count += 1
        return count

    async def flush_pending(self, product_id: str) -> int:
        """Push all PENDING signals to a freshly reconnected product."""
        signals = await self._signal_repo.get_pending_for_product(product_id)
        count = 0
        for signal in signals:
            if await self.dispatch(signal, product_id):
                count += 1
        if count:
            _log.info("signal.pending_flushed", product_id=product_id, count=count)
        return count
