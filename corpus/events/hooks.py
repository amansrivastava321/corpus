"""Pre-built event hook factories for common Corpus instrumentation patterns."""

import structlog

from corpus.events.event_bus import EventBus
from corpus.events.event_types import (
    CorpusEventType,
    ProductRegisteredEvent,
    ProductUnregisteredEvent,
    SignalAcknowledgedEvent,
    SignalEmittedEvent,
)
from corpus.runtime.state import RuntimeState

logger = structlog.get_logger()


def register_logging_hooks(bus: EventBus) -> None:
    """Wire structured log output for all Corpus events."""

    def on_product_registered(e: ProductRegisteredEvent) -> None:
        logger.info("corpus.product_registered", product_id=e.product_id, name=e.product_name)

    def on_product_unregistered(e: ProductUnregisteredEvent) -> None:
        logger.info("corpus.product_unregistered", product_id=e.product_id)

    def on_signal_emitted(e: SignalEmittedEvent) -> None:
        logger.info(
            "corpus.signal_emitted",
            signal_id=e.signal_id,
            type=e.signal_type,
            severity=e.severity,
            source=e.source_product,
            target=e.target_product,
            broadcast=e.broadcast,
        )

    def on_signal_acked(e: SignalAcknowledgedEvent) -> None:
        logger.info(
            "corpus.signal_acknowledged", signal_id=e.signal_id, product_id=e.product_id
        )

    bus.subscribe(CorpusEventType.PRODUCT_REGISTERED, on_product_registered)
    bus.subscribe(CorpusEventType.PRODUCT_UNREGISTERED, on_product_unregistered)
    bus.subscribe(CorpusEventType.SIGNAL_EMITTED, on_signal_emitted)
    bus.subscribe(CorpusEventType.SIGNAL_ACKNOWLEDGED, on_signal_acked)


def register_state_hooks(bus: EventBus, state: RuntimeState) -> None:
    """Wire runtime counter updates via events."""

    def on_product_registered(_: ProductRegisteredEvent) -> None:
        state.total_products_registered += 1

    def on_signal_emitted(_: SignalEmittedEvent) -> None:
        state.total_signals_received += 1

    bus.subscribe(CorpusEventType.PRODUCT_REGISTERED, on_product_registered)
    bus.subscribe(CorpusEventType.SIGNAL_EMITTED, on_signal_emitted)
