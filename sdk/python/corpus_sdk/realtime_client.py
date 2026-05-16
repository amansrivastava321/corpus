"""
CorpusRealtimeClient — async WebSocket client for live signal delivery.

Usage:
    import asyncio
    from corpus_sdk import CorpusClient, CorpusRealtimeClient

    async def main():
        client = CorpusClient(product_name="Anvil")
        client.connect()

        rt = client.connect_realtime()
        rt.subscribe(callback=handle_signal)
        await rt.listen()   # blocks, reconnects on disconnect

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

_log = logging.getLogger("corpus_sdk.realtime")

try:
    import websockets  # type: ignore[import-untyped]
    from websockets.exceptions import ConnectionClosed  # type: ignore[import-untyped]
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False


class CorpusRealtimeClient:
    """
    Async WebSocket client that maintains a live connection to Corpus.

    Features:
    - Automatic reconnect with exponential back-off
    - Periodic heartbeat sending
    - Signal callbacks filtered by signal type
    - Graceful shutdown via disconnect()
    """

    def __init__(
        self,
        product_id: str,
        product_name: str,
        ws_url: str,
        heartbeat_interval: int = 20,
        reconnect: bool = True,
        reconnect_max_delay: float = 30.0,
    ) -> None:
        if not _WS_AVAILABLE:
            raise ImportError(
                "websockets library is required for realtime support. "
                "Install it with: pip install websockets"
            )
        self._product_id = product_id
        self._product_name = product_name
        self._ws_url = ws_url
        self._heartbeat_interval = heartbeat_interval
        self._reconnect = reconnect
        self._reconnect_max_delay = reconnect_max_delay

        self._callbacks: list[Callable] = []
        self._signal_type_filters: list[str] | None = None
        self._ws: Any = None
        self._running = False
        self._reconnect_attempts = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subscribe(
        self,
        callback: Callable,
        signal_types: list[str] | None = None,
    ) -> None:
        """Register a callback for incoming SIGNAL messages.

        Args:
            callback:     Called with the signal dict on each incoming signal.
            signal_types: Optional whitelist of signal types (e.g. ["BLOCK", "INTERRUPT"]).
                          If None, all signal types are delivered.
        """
        self._callbacks.append(callback)
        if signal_types is not None:
            filters = [s.upper() for s in signal_types]
            self._signal_type_filters = (
                list(set((self._signal_type_filters or []) + filters))
            )

    async def listen(self) -> None:
        """Block and process incoming WebSocket messages.  Reconnects on disconnect."""
        self._running = True
        delay = 1.0
        while self._running:
            try:
                await self._connect_and_run()
                delay = 1.0
                self._reconnect_attempts = 0
            except Exception as exc:
                if not self._running:
                    break
                if not self._reconnect:
                    raise
                self._reconnect_attempts += 1
                _log.warning(
                    "corpus_realtime: disconnected (%s), reconnecting in %.1fs",
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max_delay)

    async def disconnect(self) -> None:
        """Stop listening and close the WebSocket connection."""
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def send_heartbeat(self) -> None:
        """Manually send a heartbeat frame."""
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"message_type": "HEARTBEAT"}))
            except Exception:
                pass

    async def acknowledge(self, signal_id: str) -> None:
        """Acknowledge a signal over the WebSocket connection."""
        if self._ws is not None:
            try:
                await self._ws.send(
                    json.dumps({"message_type": "ACK", "signal_id": signal_id})
                )
            except Exception:
                pass

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._running

    @property
    def reconnect_attempts(self) -> int:
        return self._reconnect_attempts

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _connect_and_run(self) -> None:
        async with websockets.connect(self._ws_url) as ws:
            self._ws = ws
            _log.info("corpus_realtime: connected to %s", self._ws_url)

            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            try:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    await self._dispatch(msg)
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                self._ws = None

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self.send_heartbeat()

    async def _dispatch(self, msg: dict) -> None:
        msg_type = msg.get("message_type", "")
        if msg_type == "SIGNAL":
            signal = msg.get("signal", {})
            sig_type = signal.get("type", "")
            if (
                self._signal_type_filters is None
                or sig_type.upper() in self._signal_type_filters
            ):
                for cb in self._callbacks:
                    try:
                        result = cb(signal)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as exc:
                        _log.error("corpus_realtime: callback error: %s", exc)
        elif msg_type == "CONNECTED":
            pending = msg.get("pending_count", 0)
            _log.info(
                "corpus_realtime: CONNECTED as %s (%d pending signals)",
                self._product_name,
                pending,
            )
        elif msg_type == "HEARTBEAT_ACK":
            pass
        elif msg_type == "PRESENCE_UPDATE":
            _log.debug(
                "corpus_realtime: presence update %s → %s",
                msg.get("product_name"),
                msg.get("status"),
            )
        elif msg_type == "ERROR":
            _log.warning(
                "corpus_realtime: server error %s: %s",
                msg.get("code"),
                msg.get("detail"),
            )
