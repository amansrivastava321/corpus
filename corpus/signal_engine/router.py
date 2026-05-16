"""Signal router — receive, route, queue, and acknowledge signals."""

from datetime import datetime, timedelta, timezone

import aiosqlite

from corpus.errors import (
    ProductNotFoundError,
    SignalAcknowledgementError,
    SignalExpiredError,
    SignalNotFoundError,
    SignalRoutingError,
)
from corpus.registry.product_registry import ProductRegistry
from corpus.schemas import Signal
from corpus.storage.repositories import DeliveryRepository, SignalRepository


class SignalRouter:
    """
    Responsibilities:
    - validate incoming signals (TTL, target resolution)
    - persist signals
    - create per-product delivery records (direct and broadcast)
    - serve pending signal queues
    - process acknowledgements
    """

    def __init__(self, conn: aiosqlite.Connection, registry: ProductRegistry) -> None:
        self._conn = conn
        self._signal_repo = SignalRepository(conn)
        self._delivery_repo = DeliveryRepository(conn)
        self._registry = registry

    async def emit(self, signal: Signal) -> Signal:
        if signal.is_expired():
            raise SignalExpiredError(signal.id)

        # Compute DB-side expiry timestamp
        expires_at: str | None = None
        if signal.ttl is not None:
            expires_at = (signal.timestamp + timedelta(seconds=signal.ttl)).isoformat()

        is_broadcast = signal.metadata.broadcast

        if is_broadcast:
            # Broadcast: deliver to all registered products except the source
            await self._signal_repo.save(signal, expires_at)
            products = await self._registry.list_products()
            for product in products:
                if (
                    product.product_id != signal.source_product
                    and product.name.lower() != signal.source_product.lower()
                ):
                    await self._delivery_repo.create(signal.id, product.product_id)
            await self._conn.commit()
        else:
            # Direct signal — target must be a registered product
            if not signal.target_product:
                raise SignalRoutingError(
                    "Non-broadcast signal must specify target_product"
                )
            try:
                target = await self._registry.get_product(signal.target_product)
            except ProductNotFoundError:
                raise SignalRoutingError(
                    f"Target product '{signal.target_product}' is not registered. "
                    "Register the product before sending it signals."
                )

            await self._signal_repo.save(signal, expires_at)
            await self._delivery_repo.create(signal.id, target.product_id)
            await self._conn.commit()

        return signal

    async def get_pending(self, identifier: str) -> list[Signal]:
        """Return non-expired pending signals for the product identified by UUID or name."""
        product = await self._registry.get_product(identifier)
        return await self._signal_repo.get_pending_for_product(product.product_id)

    async def acknowledge(self, signal_id: str, product_identifier: str) -> None:
        """Mark a signal delivery as acknowledged.

        product_identifier may be a UUID or a product name.
        """
        # Verify signal exists
        if not await self._signal_repo.get(signal_id):
            raise SignalNotFoundError(signal_id)

        # Resolve product
        product = await self._registry.get_product(product_identifier)

        # Check delivery record exists
        if not await self._delivery_repo.exists(signal_id, product.product_id):
            raise SignalAcknowledgementError(
                f"No delivery record for signal '{signal_id}' → product '{product.product_id}'. "
                "The signal may not have been routed to this product."
            )

        updated = await self._delivery_repo.acknowledge(signal_id, product.product_id)
        if not updated:
            # Already acknowledged — idempotent, not an error
            return

    async def get_signal(self, signal_id: str) -> Signal:
        signal = await self._signal_repo.get(signal_id)
        if signal is None:
            raise SignalNotFoundError(signal_id)
        return signal

    async def pending_count(self) -> int:
        return await self._signal_repo.count_pending()
