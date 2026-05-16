"""Product application service — orchestrates registry + event bus."""

from corpus.events.event_bus import EventBus
from corpus.events.event_types import (
    ProductRegisteredEvent,
    ProductUnregisteredEvent,
)
from corpus.registry.product_registry import ProductRegistry
from corpus.schemas import ProductHeartbeat, ProductRegistration


class ProductService:
    """
    Framework-independent application service for product lifecycle operations.

    Routes, SDK clients, and future WebSocket handlers all call this layer —
    never the registry directly.
    """

    def __init__(self, registry: ProductRegistry, event_bus: EventBus) -> None:
        self._registry = registry
        self._bus = event_bus

    async def register(
        self, product: ProductRegistration, update_existing: bool = False
    ) -> ProductRegistration:
        result = await self._registry.register_product(product, update_existing)
        await self._bus.publish(
            ProductRegisteredEvent(product_id=result.product_id, product_name=result.name)
        )
        return result

    async def heartbeat(self, identifier: str, beat: ProductHeartbeat) -> ProductRegistration:
        return await self._registry.heartbeat(identifier, beat)

    async def get(self, identifier: str) -> ProductRegistration:
        return await self._registry.get_product(identifier)

    async def list_all(self) -> list[ProductRegistration]:
        return await self._registry.list_products()

    async def unregister(self, identifier: str) -> None:
        product = await self._registry.get_product(identifier)
        await self._registry.unregister_product(identifier)
        await self._bus.publish(ProductUnregisteredEvent(product_id=product.product_id))
