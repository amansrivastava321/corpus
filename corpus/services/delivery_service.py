"""Delivery application service — delivery-level queries and housekeeping."""

from corpus.storage.repositories import DeliveryRepository, SignalRepository


class DeliveryService:
    """
    Exposes delivery-specific read operations used by Phase 3 WebSocket presence
    tracking and future monitoring endpoints.
    """

    def __init__(
        self,
        signal_repo: SignalRepository,
        delivery_repo: DeliveryRepository,
    ) -> None:
        self._signal_repo = signal_repo
        self._delivery_repo = delivery_repo

    async def count_pending(self) -> int:
        return await self._signal_repo.count_pending()

    async def get_delivery_status(self, signal_id: str, product_id: str) -> str | None:
        return await self._delivery_repo.get_status(signal_id, product_id)

    async def delivery_exists(self, signal_id: str, product_id: str) -> bool:
        return await self._delivery_repo.exists(signal_id, product_id)

    async def get_delivery_stats(self) -> dict:
        pending = await self._signal_repo.count_pending()
        return {
            "pending": pending,
        }
