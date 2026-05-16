"""SDK tests — run the full client against a real in-memory Corpus server."""

import pytest
from fastapi.testclient import TestClient

from corpus.server import create_app
from corpus_sdk import CorpusClient, InProcessTransport
from corpus_sdk.exceptions import (
    ProductAlreadyRegisteredError,
    SignalAcknowledgementError,
    SignalNotFoundError,
    SignalRoutingError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server():
    """In-memory Corpus server per test."""
    with TestClient(create_app(db_path=":memory:")) as tc:
        yield tc


def make_client(server, name: str = "test-product", **kwargs) -> CorpusClient:
    return CorpusClient(
        product_name=name,
        transport=InProcessTransport(server),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestSDKRegistration:
    def test_connect_registers_product(self, server):
        client = make_client(server, "Anvil")
        product = client.connect()
        assert product.name == "Anvil"
        assert product.product_id is not None
        assert client.is_connected

    def test_connect_stores_product_info(self, server):
        client = make_client(server, "Anvil")
        client.connect()
        assert client.product is not None
        assert client.product_id is not None

    def test_connect_duplicate_raises(self, server):
        c1 = make_client(server, "Anvil")
        c2 = make_client(server, "Anvil")
        c1.connect()
        with pytest.raises(ProductAlreadyRegisteredError):
            c2.connect()

    def test_connect_update_existing(self, server):
        c1 = make_client(server, "Anvil", product_version="1.0.0")
        c1.connect()
        c2 = make_client(server, "Anvil", product_version="2.0.0")
        product = c2.connect(update_existing=True)
        assert product.version == "2.0.0"
        # Original product_id preserved
        assert product.product_id == c1.product_id

    def test_connect_with_description(self, server):
        client = make_client(server, "Anvil")
        product = client.connect(description="AI dev orchestration")
        assert product.name == "Anvil"

    def test_connect_with_capabilities(self, server):
        client = CorpusClient(
            product_name="Inspectra",
            capabilities=["EMIT_SIGNALS", "AUDIT", "INTERRUPT"],
            transport=InProcessTransport(server),
        )
        product = client.connect()
        assert "AUDIT" in product.capabilities

    def test_disconnect_unregisters_product(self, server):
        client = make_client(server, "Anvil")
        client.connect()
        client.disconnect()
        assert not client.is_connected
        # Verify removed from registry
        resp = server.get("/products/Anvil")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


class TestSDKHeartbeat:
    def test_heartbeat_returns_product_info(self, server):
        client = make_client(server, "Anvil")
        client.connect()
        product = client.heartbeat()
        assert product.name == "Anvil"
        assert product.last_seen is not None

    def test_heartbeat_with_degraded_status(self, server):
        client = make_client(server, "Anvil")
        client.connect()
        product = client.heartbeat(status="DEGRADED")
        assert product.status == "DEGRADED"


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------


class TestSDKSignalEmit:
    def test_emit_inform_signal(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()

        result = sender.emit_signal("INFORM", "LOW", target="Anvil", payload={"msg": "hello"})
        assert result.id is not None
        assert result.signal_type == "INFORM"
        assert result.severity == "LOW"

    def test_emit_to_unknown_target_raises(self, server):
        client = make_client(server, "Inspectra")
        client.connect()
        with pytest.raises(SignalRoutingError):
            client.emit_signal("BLOCK", "CRITICAL", target="ghost-product")

    def test_emit_accepts_lowercase_type_and_severity(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()
        result = sender.emit_signal("inform", "low", target="Anvil")
        assert result.signal_type == "INFORM"

    def test_emit_with_intent_shorthand(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()
        result = sender.emit_signal(
            "CONSULT", "MEDIUM", target="Anvil", intent="Is this auth refactor safe?"
        )
        assert "intent" in result.payload

    def test_emit_with_ttl(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()
        result = sender.emit_signal("INFORM", "LOW", target="Anvil", ttl=300)
        assert result.id is not None


# ---------------------------------------------------------------------------
# Convenience signal methods
# ---------------------------------------------------------------------------


class TestSDKConvenienceMethods:
    def _setup(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        server.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})
        return sender

    def test_inform(self, server):
        client = self._setup(server)
        result = client.inform("Anvil", "Analysis started")
        assert result.signal_type == "INFORM"

    def test_consult(self, server):
        client = self._setup(server)
        result = client.consult("Anvil", "Is this safe?", {"context": "auth refactor"})
        assert result.signal_type == "CONSULT"

    def test_interrupt(self, server):
        client = self._setup(server)
        result = client.interrupt("Anvil", "SQL injection risk detected")
        assert result.signal_type == "INTERRUPT"
        assert result.severity == "HIGH"

    def test_block(self, server):
        client = self._setup(server)
        result = client.block("Anvil", "Hardcoded secret found")
        assert result.signal_type == "BLOCK"
        assert result.severity == "CRITICAL"

    def test_validate(self, server):
        client = self._setup(server)
        result = client.validate("Anvil", {"artifact_ref": "pr/123"})
        assert result.signal_type == "VALIDATE"

    def test_learn_is_broadcast(self, server):
        client = self._setup(server)
        result = client.learn("hardcoded_secret", {"frequency": 3})
        assert result.signal_type == "LEARN"
        assert result.broadcast is True

    def test_escalate_is_broadcast(self, server):
        client = self._setup(server)
        result = client.escalate("Unresolved for 10min")
        assert result.signal_type == "ESCALATE"
        assert result.broadcast is True


# ---------------------------------------------------------------------------
# Pending and acknowledgement
# ---------------------------------------------------------------------------


class TestSDKPendingAndAck:
    def test_get_pending_signals(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()

        sender.emit_signal("INFORM", "LOW", target="Anvil")
        pending = receiver.get_pending_signals()
        assert len(pending) == 1
        assert pending[0].source_product == "Inspectra"

    def test_acknowledge_clears_pending(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()

        sender.emit_signal("INFORM", "LOW", target="Anvil")
        signals = receiver.get_pending_signals()
        assert len(signals) == 1
        receiver.acknowledge_signal(signals[0].id)
        assert len(receiver.get_pending_signals()) == 0

    def test_process_pending_calls_handler(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()

        sender.emit_signal("INFORM", "LOW", target="Anvil")
        sender.emit_signal("INFORM", "LOW", target="Anvil")

        received = []
        count = receiver.process_pending(handler=lambda s: received.append(s.signal_type))
        assert count == 2
        assert received == ["INFORM", "INFORM"]
        assert len(receiver.get_pending_signals()) == 0

    def test_ack_wrong_product_raises(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()
        third = make_client(server, "GraphEngine")
        third.connect()

        sender.emit_signal("INFORM", "LOW", target="Anvil")
        signals = receiver.get_pending_signals()
        with pytest.raises(SignalAcknowledgementError):
            third.acknowledge_signal(signals[0].id)

    def test_get_signal_by_id(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()

        emitted = sender.emit_signal("INFORM", "LOW", target="Anvil")
        fetched = receiver.get_signal(emitted.id)
        assert fetched.id == emitted.id

    def test_get_nonexistent_signal_raises(self, server):
        client = make_client(server, "Anvil")
        client.connect()
        with pytest.raises(SignalNotFoundError):
            client.get_signal("no-such-signal")


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------


class TestSDKBroadcast:
    def test_broadcast_learn_reaches_all(self, server):
        source = make_client(server, "Inspectra")
        source.connect()
        r1 = make_client(server, "Anvil")
        r1.connect()
        r2 = make_client(server, "GraphEngine")
        r2.connect()

        source.learn("hardcoded_secret", {"files": ["auth/config.py"]})

        assert len(r1.get_pending_signals()) == 1
        assert len(r2.get_pending_signals()) == 1
        # source itself should not receive its own broadcast
        assert len(source.get_pending_signals()) == 0


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestSDKHealth:
    def test_get_health(self, server):
        client = make_client(server, "Anvil")
        health = client.get_health()
        assert health.status == "ok"
        assert health.version == "0.1.0"
        assert health.uptime_seconds >= 0

    def test_health_increments_after_activity(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()

        h1 = sender.get_health()
        sender.emit_signal("INFORM", "LOW", target="Anvil")
        h2 = sender.get_health()
        assert h2.total_signals_received > h1.total_signals_received


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


class TestSDKHooks:
    def test_on_signal_emitted_hook_fires(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        server.post("/products/register", json={"name": "Anvil", "version": "1.0.0"})

        emitted_signals = []

        @sender.hooks.on_signal_emitted
        def capture(sig):
            emitted_signals.append(sig.signal_type)

        sender.emit_signal("INFORM", "LOW", target="Anvil")
        assert emitted_signals == ["INFORM"]

    def test_on_signal_received_hook_fires(self, server):
        sender = make_client(server, "Inspectra")
        sender.connect()
        receiver = make_client(server, "Anvil")
        receiver.connect()

        received = []

        @receiver.hooks.on_signal_received
        def capture(sig):
            received.append(sig.signal_type)

        sender.emit_signal("INFORM", "LOW", target="Anvil")
        receiver.get_pending_signals()
        assert received == ["INFORM"]


# ---------------------------------------------------------------------------
# Retry / connection error
# ---------------------------------------------------------------------------


class TestSDKTransportErrors:
    def test_connection_error_raised_for_unreachable_server(self):
        from corpus_sdk import CorpusConnectionError
        from corpus_sdk.transport import HTTPTransport

        transport = HTTPTransport(base_url="http://localhost:19999", retries=1, retry_delay=0)
        client = CorpusClient(product_name="ghost", transport=transport)
        with pytest.raises(CorpusConnectionError):
            client.get_health()
