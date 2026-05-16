"""
InterruptBridge — reactively blocks waiting checkpoints when a signal is emitted.

When a BLOCK/INTERRUPT/ESCALATE signal is emitted, the bridge checks if any
products have checkpoints in WAITING_CLEARANCE status and immediately issues a
decision for them.

This is the reactive path. The proactive path is ClearanceEngine.evaluate()
called by CheckpointService.request_clearance().
"""

from __future__ import annotations

from corpus import log
from corpus.checkpoints.models import RuntimeDecisionType
from corpus.events.event_bus import EventBus
from corpus.events.event_types import CorpusEventType, SignalEmittedEvent
from corpus.interrupts.interrupt_rules import InterruptRules
from corpus.schemas.signal import SignalType

_log = log.get_logger("corpus.interrupt_bridge")

# Signal types that can reactively block waiting checkpoints
_REACTIVE_TYPES = {SignalType.BLOCK.value, SignalType.INTERRUPT.value, SignalType.ESCALATE.value}


class InterruptBridge:
    """
    Subscribes to SIGNAL_EMITTED events and reactively governs waiting checkpoints.

    Injected with a lazy getter for CheckpointService to break the circular
    initialization: CheckpointService → InterruptBridge → CheckpointService.
    """

    def __init__(
        self,
        event_bus: EventBus,
        rules: InterruptRules | None = None,
    ) -> None:
        self._bus = event_bus
        self._rules = rules or InterruptRules()
        self._checkpoint_service_getter = None
        self._bus.subscribe(CorpusEventType.SIGNAL_EMITTED, self._on_signal_emitted)

    def set_checkpoint_service(self, getter) -> None:
        """Late-bind the checkpoint service getter to avoid circular imports."""
        self._checkpoint_service_getter = getter

    async def _on_signal_emitted(self, event: SignalEmittedEvent) -> None:
        if event.signal_type not in _REACTIVE_TYPES:
            return
        if self._checkpoint_service_getter is None:
            return

        svc = self._checkpoint_service_getter()
        if svc is None:
            return

        # Find waiting checkpoints for the target product
        target = event.target_product or ""
        if not target:
            return  # broadcast — not directly targeted at a single product

        try:
            waiting = await svc.list_all(status="WAITING_CLEARANCE")
        except Exception:
            return

        for checkpoint in waiting:
            # Check if this checkpoint belongs to the target product
            if checkpoint.product_id == target or checkpoint.product_name.lower() == target.lower():
                _log.info(
                    "interrupt_bridge.reactive_block",
                    checkpoint_id=checkpoint.id,
                    signal_id=event.signal_id,
                    signal_type=event.signal_type,
                )
                try:
                    # Re-evaluate (will pick up the new signal)
                    await svc.request_clearance(checkpoint.id, reactive=True)
                except Exception as exc:
                    _log.warning(
                        "interrupt_bridge.reactive_block_failed",
                        checkpoint_id=checkpoint.id,
                        error=str(exc),
                    )
