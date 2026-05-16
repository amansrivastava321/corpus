from typing import Protocol

from corpus.schemas import ProductHeartbeat, ProductRegistration


class RegistryInterface(Protocol):
    """Structural interface for product registries.

    Any object satisfying this protocol can serve as a registry — SQLite-backed,
    in-memory, distributed, or mock implementations are all valid.
    """

    async def register_product(
        self, product: ProductRegistration, update_existing: bool = False
    ) -> ProductRegistration: ...

    async def get_product(self, identifier: str) -> ProductRegistration: ...

    async def list_products(self) -> list[ProductRegistration]: ...

    async def heartbeat(
        self, identifier: str, beat: ProductHeartbeat
    ) -> ProductRegistration: ...

    async def is_registered(self, identifier: str) -> bool: ...

    async def unregister_product(self, identifier: str) -> None: ...
