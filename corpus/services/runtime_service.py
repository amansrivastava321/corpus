"""Runtime service — health reporting and session state."""

from corpus.config import VERSION
from corpus.registry.product_registry import ProductRegistry
from corpus.runtime.state import RuntimeState
from corpus.signal_engine.router import SignalRouter


class RuntimeService:
    def __init__(
        self,
        state: RuntimeState,
        registry: ProductRegistry,
        router: SignalRouter,
    ) -> None:
        self._state = state
        self._registry = registry
        self._router = router

    async def get_health(self) -> dict:
        products = await self._registry.list_products()
        pending = await self._router.pending_count()
        return {
            "status": "ok",
            "version": VERSION,
            "products_registered": len(products),
            "pending_deliveries": pending,
            **self._state.to_dict(),
        }

    @property
    def state(self) -> RuntimeState:
        return self._state
