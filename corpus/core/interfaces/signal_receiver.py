from typing import Protocol

from corpus.schemas import Signal


class SignalReceiver(Protocol):
    """Any object that can receive and acknowledge signals."""

    async def get_pending(self, identifier: str) -> list[Signal]: ...

    async def acknowledge(self, signal_id: str, product_identifier: str) -> None: ...
