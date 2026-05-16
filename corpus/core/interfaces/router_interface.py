from typing import Protocol

from corpus.schemas import Signal


class RouterInterface(Protocol):
    """Structural interface for signal routers."""

    async def emit(self, signal: Signal) -> Signal: ...

    async def get_pending(self, identifier: str) -> list[Signal]: ...

    async def acknowledge(self, signal_id: str, product_identifier: str) -> None: ...

    async def get_signal(self, signal_id: str) -> Signal: ...

    async def pending_count(self) -> int: ...
