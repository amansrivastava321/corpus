"""Signal application service — orchestrates router + event bus."""

from corpus.events.event_bus import EventBus
from corpus.events.event_types import SignalAcknowledgedEvent, SignalEmittedEvent
from corpus.schemas import Signal
from corpus.signal_engine.router import SignalRouter


class SignalService:
    """
    Framework-independent application service for signal lifecycle operations.

    Routes, SDK, and WebSocket handlers all call this — never the router directly.
    """

    def __init__(self, router: SignalRouter, event_bus: EventBus) -> None:
        self._router = router
        self._bus = event_bus

    async def emit(self, signal: Signal) -> Signal:
        result = await self._router.emit(signal)
        await self._bus.publish(
            SignalEmittedEvent(
                signal_id=result.id,
                signal_type=result.type.value,
                severity=result.severity.value,
                source_product=result.source_product,
                target_product=result.target_product,
                broadcast=result.metadata.broadcast,
            )
        )
        return result

    async def get_pending(self, identifier: str) -> list[Signal]:
        return await self._router.get_pending(identifier)

    async def acknowledge(self, signal_id: str, product_identifier: str) -> None:
        await self._router.acknowledge(signal_id, product_identifier)
        await self._bus.publish(
            SignalAcknowledgedEvent(signal_id=signal_id, product_id=product_identifier)
        )

    async def get(self, signal_id: str) -> Signal:
        return await self._router.get_signal(signal_id)

    async def pending_count(self) -> int:
        return await self._router.pending_count()
