"""
CorpusClient — the main developer-facing SDK class.

Designed for elegance: minimal setup, strong types, helpful convenience methods.

Quick start:

    from corpus_sdk import CorpusClient

    client = CorpusClient(product_name="anvil")
    client.connect()

    client.inform("inspectra", "Starting auth module analysis", {"files": ["auth/login.py"]})
    client.consult("inspectra", "Is JWT migration safe?", {"context": "replacing uuid4 tokens"})

    for signal in client.get_pending_signals():
        print(signal.signal_type, signal.payload)
        client.acknowledge_signal(signal.id)
"""

from __future__ import annotations

from typing import Any

from corpus_sdk.config import CorpusConfig
from corpus_sdk.exceptions import NotConnectedError
from corpus_sdk.hooks import HookRegistry
from corpus_sdk.models import EmittedSignal, HealthInfo, ProductInfo, ReceivedSignal
from corpus_sdk.transport import BaseTransport, HTTPTransport


class CorpusClient:
    """
    Synchronous Corpus SDK client.

    Args:
        product_name:    Name used to register this product in Corpus.
        product_version: Semantic version of the connecting product.
        capabilities:    List of Corpus capability strings this product supports.
        base_url:        Corpus daemon base URL (default: http://localhost:8000).
        timeout:         HTTP request timeout in seconds.
        retries:         Number of retry attempts on connection failure.
        transport:       Override the transport — use InProcessTransport for tests.
    """

    def __init__(
        self,
        product_name: str,
        product_version: str = "0.1.0",
        capabilities: list[str] | None = None,
        base_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        retries: int = 3,
        transport: BaseTransport | None = None,
    ) -> None:
        self._product_name = product_name
        self._product_version = product_version
        self._capabilities = capabilities or ["EMIT_SIGNALS", "RECEIVE_SIGNALS"]
        self._transport = transport or HTTPTransport(
            base_url=base_url, timeout=timeout, retries=retries
        )
        self._product: ProductInfo | None = None
        self.hooks = HookRegistry()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(
        self,
        description: str | None = None,
        update_existing: bool = False,
        **metadata: Any,
    ) -> ProductInfo:
        """Register this product with Corpus and return the ProductInfo.

        Call this once at startup. After connect(), the client remembers
        its product_id for pending-signal retrieval and acknowledgements.
        """
        payload: dict[str, Any] = {
            "name": self._product_name,
            "version": self._product_version,
            "capabilities": self._capabilities,
        }
        if description:
            payload["description"] = description
        if metadata:
            payload["metadata"] = metadata

        qs = "?update_existing=true" if update_existing else ""
        data = self._transport.post(f"/products/register{qs}", json=payload)
        self._product = ProductInfo.from_dict(data)
        return self._product

    def disconnect(self) -> None:
        """Unregister this product from Corpus."""
        if self._product:
            self._transport.delete(f"/products/{self._product.product_id}")
            self._product = None

    def heartbeat(self, status: str = "ACTIVE") -> ProductInfo:
        """Send a heartbeat to signal this product is alive."""
        identifier = self._resolved_identifier()
        data = self._transport.post(
            f"/products/{identifier}/heartbeat",
            json={"product_id": identifier, "status": status},
        )
        if self._product:
            self._product.status = status
        return ProductInfo.from_dict(data)

    # ------------------------------------------------------------------
    # Signal emission
    # ------------------------------------------------------------------

    def emit_signal(
        self,
        signal_type: str,
        severity: str,
        payload: dict[str, Any] | None = None,
        target: str | None = None,
        broadcast: bool = False,
        tags: list[str] | None = None,
        requires_ack: bool = False,
        ttl: int | None = None,
        correlation_id: str | None = None,
        intent: str | None = None,
    ) -> EmittedSignal:
        """Emit a typed signal into the Corpus runtime.

        Args:
            signal_type:    One of INFORM, CONSULT, INTERRUPT, BLOCK, VALIDATE, LEARN, ESCALATE.
            severity:       One of LOW, MEDIUM, HIGH, CRITICAL.
            payload:        Arbitrary signal data.
            target:         Target product name or ID (mutually exclusive with broadcast).
            broadcast:      If True, route to all products except this one.
            tags:           Optional string tags for filtering and observability.
            requires_ack:   If True, signal must be acknowledged.
            ttl:            Seconds until this signal expires.
            correlation_id: Link this signal to a group of related signals.
            intent:         Shorthand description — added to payload["intent"].
        """
        merged_payload: dict[str, Any] = dict(payload or {})
        if intent:
            merged_payload.setdefault("intent", intent)

        body: dict[str, Any] = {
            "type": signal_type.upper(),
            "severity": severity.upper(),
            "source_product": self._product_name,
            "payload": merged_payload,
            "metadata": {
                "broadcast": broadcast,
                "requires_ack": requires_ack,
                "tags": tags or [],
            },
        }
        if not broadcast:
            body["target_product"] = target
        if ttl is not None:
            body["ttl"] = ttl
        if correlation_id:
            body["correlation_id"] = correlation_id

        self.hooks.fire_pre_emit(body)
        data = self._transport.post("/signals/emit", json=body)
        result = EmittedSignal.from_dict(data)
        self.hooks.fire_post_emit(result)
        return result

    # ------------------------------------------------------------------
    # Signal reception
    # ------------------------------------------------------------------

    def get_pending_signals(self) -> list[ReceivedSignal]:
        """Poll for signals waiting for this product."""
        identifier = self._resolved_identifier()
        data = self._transport.get(f"/signals/pending/{identifier}")
        signals = [ReceivedSignal.from_dict(s) for s in (data or [])]
        for sig in signals:
            self.hooks.fire_signal_received(sig)
        return signals

    def acknowledge_signal(self, signal_id: str) -> None:
        """Acknowledge receipt of a signal — removes it from the pending queue."""
        identifier = self._resolved_identifier()
        self._transport.post(
            f"/signals/{signal_id}/ack",
            json={"product_id": identifier},
        )
        self.hooks.fire_acknowledged(signal_id)

    def get_signal(self, signal_id: str) -> ReceivedSignal:
        """Retrieve a specific signal by ID."""
        data = self._transport.get(f"/signals/{signal_id}")
        return ReceivedSignal.from_dict(data)

    def process_pending(self, handler=None) -> int:
        """Poll, optionally process via handler, then acknowledge all pending signals.

        Args:
            handler: Optional callable(signal) — called before acknowledgement.
        Returns:
            Number of signals processed.
        """
        signals = self.get_pending_signals()
        for sig in signals:
            if handler:
                handler(sig)
            self.acknowledge_signal(sig.id)
        return len(signals)

    # ------------------------------------------------------------------
    # Convenience signal constructors
    # ------------------------------------------------------------------

    def inform(
        self, target: str, message: str, payload: dict | None = None, **kwargs
    ) -> EmittedSignal:
        return self.emit_signal(
            "INFORM", "LOW", target=target,
            payload={"message": message, **(payload or {})}, **kwargs,
        )

    def consult(
        self, target: str, question: str, context: dict | None = None, severity: str = "MEDIUM",
    ) -> EmittedSignal:
        return self.emit_signal(
            "CONSULT", severity, target=target,
            payload={"question": question, "context": context or {}},
            requires_ack=True,
        )

    def interrupt(
        self, target: str, reason: str, severity: str = "HIGH", evidence: dict | None = None,
    ) -> EmittedSignal:
        return self.emit_signal(
            "INTERRUPT", severity, target=target,
            payload={"reason": reason, "evidence": evidence or {}},
            requires_ack=True,
        )

    def block(
        self, target: str, reason: str, evidence: dict | None = None,
    ) -> EmittedSignal:
        return self.emit_signal(
            "BLOCK", "CRITICAL", target=target,
            payload={"reason": reason, "evidence": evidence or {}},
            requires_ack=True,
        )

    def validate(
        self, target: str, artifact: dict, scope: list[str] | None = None, severity: str = "MEDIUM",
    ) -> EmittedSignal:
        return self.emit_signal(
            "VALIDATE", severity, target=target,
            payload={"artifact": artifact, "scope": scope or ["security", "correctness"]},
            requires_ack=True,
        )

    def learn(
        self, pattern: str, details: dict | None = None,
    ) -> EmittedSignal:
        return self.emit_signal(
            "LEARN", "LOW", broadcast=True,
            payload={"pattern": pattern, **(details or {})},
        )

    def escalate(
        self, reason: str, context: dict | None = None,
    ) -> EmittedSignal:
        return self.emit_signal(
            "ESCALATE", "CRITICAL", broadcast=True,
            payload={"reason": reason, "context": context or {}},
            requires_ack=True,
        )

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    def get_health(self) -> HealthInfo:
        data = self._transport.get("/health")
        return HealthInfo.from_dict(data)

    # ------------------------------------------------------------------
    # Checkpoint governance
    # ------------------------------------------------------------------

    def checkpoints(self) -> "CheckpointClient":
        """Return a CheckpointClient scoped to this transport.

        The client must be connected (connect() called) before using checkpoints.
        """
        from corpus_sdk.checkpoint_client import CheckpointClient

        if not self.is_connected:
            raise NotConnectedError("Call connect() before using checkpoints()")
        return CheckpointClient(self._transport)

    # ------------------------------------------------------------------
    # Intelligence: gravity / translation / memory / policy
    # ------------------------------------------------------------------

    def gravity(self) -> "GravityClient":
        from corpus_sdk.gravity_client import GravityClient
        if not self.is_connected:
            raise NotConnectedError("Call connect() before using gravity()")
        return GravityClient(self._transport)

    def translator(self) -> "TranslationClient":
        from corpus_sdk.translation_client import TranslationClient
        if not self.is_connected:
            raise NotConnectedError("Call connect() before using translator()")
        return TranslationClient(self._transport)

    def memory(self) -> "MemoryClient":
        from corpus_sdk.memory_client import MemoryClient
        if not self.is_connected:
            raise NotConnectedError("Call connect() before using memory()")
        return MemoryClient(self._transport)

    def policy(self) -> "PolicyClient":
        from corpus_sdk.policy_client import PolicyClient
        if not self.is_connected:
            raise NotConnectedError("Call connect() before using policy()")
        return PolicyClient(self._transport)

    # ------------------------------------------------------------------
    # Realtime
    # ------------------------------------------------------------------

    def connect_realtime(
        self,
        ws_base_url: str | None = None,
        heartbeat_interval: int = 20,
        reconnect: bool = True,
    ) -> "CorpusRealtimeClient":
        """Return a CorpusRealtimeClient for live WebSocket signal delivery.

        The client must be connected (connect() called) before calling this.
        Call ``await rt.listen()`` in an async context to start receiving signals.

        Args:
            ws_base_url:        Override WebSocket base URL (default: derived from transport).
            heartbeat_interval: Seconds between heartbeat sends.
            reconnect:          Automatically reconnect on disconnect.
        """
        from corpus_sdk.realtime_client import CorpusRealtimeClient

        if not self.is_connected:
            raise NotConnectedError("Call connect() before connect_realtime()")

        if ws_base_url is None:
            base = getattr(self._transport, "base_url", "http://localhost:8000")
            ws_base_url = base.replace("https://", "wss://").replace("http://", "ws://")

        ws_url = f"{ws_base_url}/ws/products/{self.product_id}"
        return CorpusRealtimeClient(
            product_id=self.product_id,  # type: ignore[arg-type]
            product_name=self._product_name,
            ws_url=ws_url,
            heartbeat_interval=heartbeat_interval,
            reconnect=reconnect,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def product(self) -> ProductInfo | None:
        return self._product

    @property
    def product_id(self) -> str | None:
        return self._product.product_id if self._product else None

    @property
    def is_connected(self) -> bool:
        return self._product is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolved_identifier(self) -> str:
        if self._product:
            return self._product.product_id
        return self._product_name

    @classmethod
    def from_config(cls, product_name: str, cfg: CorpusConfig, **kwargs) -> "CorpusClient":
        return cls(
            product_name=product_name,
            base_url=cfg.base_url,
            timeout=cfg.timeout,
            retries=cfg.retries,
            **kwargs,
        )
