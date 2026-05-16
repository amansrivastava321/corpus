"""Manages active WebSocket connections: product_id → WebSocket."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from corpus.websocket.message_types import WsMessage

if TYPE_CHECKING:
    from starlette.websockets import WebSocket


class ConnectionManager:
    """
    Thread/async-safe registry of live WebSocket connections.

    Maps product_id (UUID) to its WebSocket.  A product can hold at most one
    simultaneous connection — a new connect() for the same product_id replaces
    the old one after closing it gracefully.
    """

    def __init__(self) -> None:
        self._connections: dict[str, Any] = {}  # product_id → WebSocket
        self._lock = asyncio.Lock()

    async def connect(self, product_id: str, websocket: Any) -> None:
        async with self._lock:
            old = self._connections.get(product_id)
            if old is not None and old is not websocket:
                try:
                    await old.close(code=1001)
                except Exception:
                    pass
            self._connections[product_id] = websocket

    async def disconnect(self, product_id: str) -> None:
        async with self._lock:
            self._connections.pop(product_id, None)

    def is_connected(self, product_id: str) -> bool:
        return product_id in self._connections

    def get_connection(self, product_id: str) -> Any | None:
        return self._connections.get(product_id)

    async def send_message(self, product_id: str, message: WsMessage) -> bool:
        """Send a structured message to a connected product. Returns True on success."""
        ws = self._connections.get(product_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message.model_dump())
            return True
        except Exception:
            await self.disconnect(product_id)
            return False

    async def send_raw(self, product_id: str, data: dict) -> bool:
        """Send a raw dict (pre-serialised) to a product."""
        ws = self._connections.get(product_id)
        if ws is None:
            return False
        try:
            await ws.send_json(data)
            return True
        except Exception:
            await self.disconnect(product_id)
            return False

    async def broadcast(
        self, message: WsMessage, exclude_product_id: str | None = None
    ) -> int:
        """Broadcast a message to all connected products. Returns delivery count."""
        targets = [
            pid for pid in list(self._connections)
            if pid != exclude_product_id
        ]
        count = 0
        for pid in targets:
            if await self.send_message(pid, message):
                count += 1
        return count

    def active_products(self) -> list[str]:
        return list(self._connections.keys())

    def active_count(self) -> int:
        return len(self._connections)
