"""
Base adapter — the integration contract for products connecting to Corpus.

Products subclass CorpusAdapter (or use CorpusClient directly) to integrate
with the Corpus ecosystem. Adapters are reference examples: they show the
integration pattern but contain zero Corpus-core business logic.
"""

from __future__ import annotations

from typing import Any, Callable

from corpus_sdk.client import CorpusClient
from corpus_sdk.models import EmittedSignal, ProductInfo, ReceivedSignal
from corpus_sdk.transport import BaseTransport


class CorpusAdapter:
    """
    Base adapter for products integrating with Corpus.

    Wraps a CorpusClient and adds:
    - default capability declaration
    - connect/disconnect lifecycle helpers
    - process_pending loop with overridable handle_signal()

    Subclasses override _default_capabilities() and handle_signal() to provide
    product-specific behaviour.
    """

    #: Override in subclass to declare default product capabilities.
    DEFAULT_NAME: str = "product"
    DEFAULT_VERSION: str = "0.1.0"
    DEFAULT_CAPABILITIES: list[str] = ["EMIT_SIGNALS", "RECEIVE_SIGNALS"]

    def __init__(
        self,
        client: CorpusClient | None = None,
        corpus_url: str = "http://localhost:8000",
        transport: BaseTransport | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            self._client = CorpusClient(
                product_name=self.DEFAULT_NAME,
                product_version=self.DEFAULT_VERSION,
                capabilities=list(self.DEFAULT_CAPABILITIES),
                base_url=corpus_url,
                transport=transport,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self, description: str | None = None, **metadata: Any) -> ProductInfo:
        return self._client.connect(description=description, **metadata)

    def disconnect(self) -> None:
        self._client.disconnect()

    def heartbeat(self, status: str = "ACTIVE") -> ProductInfo:
        return self._client.heartbeat(status)

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def emit(
        self,
        signal_type: str,
        severity: str,
        target: str | None = None,
        payload: dict | None = None,
        broadcast: bool = False,
        **kwargs: Any,
    ) -> EmittedSignal:
        return self._client.emit_signal(
            signal_type=signal_type,
            severity=severity,
            target=target,
            payload=payload or {},
            broadcast=broadcast,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Receive
    # ------------------------------------------------------------------

    def receive(self) -> list[ReceivedSignal]:
        return self._client.get_pending_signals()

    def acknowledge(self, signal_id: str) -> None:
        self._client.acknowledge_signal(signal_id)

    def process_pending(self, handler: Callable | None = None) -> int:
        """Poll, call handler (or handle_signal), then acknowledge."""
        signals = self.receive()
        for sig in signals:
            fn = handler or self.handle_signal
            fn(sig)
            self.acknowledge(sig.id)
        return len(signals)

    def handle_signal(self, signal: ReceivedSignal) -> None:
        """Override to add product-specific signal handling logic."""

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def client(self) -> CorpusClient:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected
