"""Product registry — single source of truth for all registered products."""

from datetime import datetime, timezone

import aiosqlite

from corpus.errors import ProductAlreadyRegisteredError, ProductNotFoundError
from corpus.schemas import ProductHeartbeat, ProductRegistration
from corpus.storage.repositories import ProductRepository


class ProductRegistry:
    """
    Business-logic layer over ProductRepository.

    Responsibilities:
    - enforce uniqueness (by name) on registration
    - support optional upsert via update_existing
    - process heartbeats and staleness checks
    - resolve products by UUID or name
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._repo = ProductRepository(conn)

    async def register_product(
        self, product: ProductRegistration, update_existing: bool = False
    ) -> ProductRegistration:
        existing = await self._repo.get_by_name(product.name)
        if existing:
            if not update_existing:
                raise ProductAlreadyRegisteredError(existing.product_id)
            # Upsert: preserve original product_id, update everything else
            updated = product.model_copy(update={"product_id": existing.product_id})
            await self._repo.update(updated)
            return updated

        await self._repo.save(product)
        return product

    async def get_product(self, identifier: str) -> ProductRegistration:
        """Resolve by UUID first, then by name (case-insensitive)."""
        product = await self._repo.get_by_id(identifier)
        if product is None:
            product = await self._repo.get_by_name(identifier)
        if product is None:
            raise ProductNotFoundError(identifier)
        return product

    async def list_products(self) -> list[ProductRegistration]:
        return await self._repo.list_all()

    async def heartbeat(
        self, identifier: str, beat: ProductHeartbeat
    ) -> ProductRegistration:
        product = await self.get_product(identifier)
        product.last_seen = datetime.now(timezone.utc)
        product.status = beat.status
        await self._repo.update(product)
        return product

    async def is_registered(self, identifier: str) -> bool:
        try:
            await self.get_product(identifier)
            return True
        except ProductNotFoundError:
            return False

    async def unregister_product(self, identifier: str) -> None:
        product = await self.get_product(identifier)
        await self._repo.delete(product.product_id)
